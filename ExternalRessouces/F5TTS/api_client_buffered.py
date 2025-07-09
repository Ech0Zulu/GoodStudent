# --- START OF REVISED SCRIPT ---

import socket
import sys
import argparse
import os
import time
import re
import threading
import queue
import numpy as np
import sounddevice as sd
from tqdm import tqdm

# ====== CONFIGURATION ======
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 9998
SAMPLE_RATE = 24000
OVERLAP_MS = 150
SOCKET_TIMEOUT = 60.0 
THREAD_JOIN_TIMEOUT = 10.0 # Reduced for faster exit if threads hang

# ====== GLOBAL VARIABLES ======
raw_audio_queue = queue.Queue()
playback_audio_buffer = np.array([], dtype=np.float32)
current_playback_position = 0
audio_buffer_lock = threading.Lock()
pending_chunks_map = {}
next_expected_chunk_index = 0
all_fetch_threads_done_event = threading.Event()
playback_finished_event = threading.Event()
stop_processing_event = threading.Event() 
progress_bars = [] 
total_sentence_count = 0
active_sockets = [] 
active_sockets_lock = threading.Lock()

FLOAT_SIZE = np.dtype(np.float32).itemsize

overlap_samples = int(SAMPLE_RATE * OVERLAP_MS / 1000)
fade_out_curve = np.linspace(1.0, 0.0, overlap_samples, dtype=np.float32)
fade_in_curve = np.linspace(0.0, 1.0, overlap_samples, dtype=np.float32)

audio_processor_thread_ref = None
fetcher_threads_ref = []
audio_output_stream_ref = None
was_interrupted_by_user = False
# Flag to indicate if the final cleanup (closing bars) has been done
final_bar_cleanup_done = False
final_bar_cleanup_lock = threading.Lock()


def split_text_into_sentences(text: str) -> list:
    return re.split(r'(?<=[.?!])\s+', text.strip())


def fetch_sentence_audio_data(sentence: str, pbar: tqdm, index: int, server_ip: str, server_port: int):
    # ... (fetch_sentence_audio_data remains largely the same as the previous version)
    # Key change: No pbar.close() here. Let cleanup_resources handle it.
    # Ensure pbar description and color reflect final state.
    global raw_audio_queue, active_sockets, active_sockets_lock, FLOAT_SIZE
    audio_data_bytes = bytearray()
    client_socket = None
    operation_successful = False 
    final_desc_set = False
    # Store received_byte_count for final pbar description
    current_received_byte_count = 0


    try:
        pbar.set_description(f"Chunk {index+1:02d} (Connecting)")
        pbar.refresh()
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(SOCKET_TIMEOUT)

        with active_sockets_lock:
            active_sockets.append(client_socket)

        client_socket.connect((server_ip, server_port))
        
        pbar.set_description(f"Chunk {index+1:02d} (Sending)")
        pbar.refresh()
        client_socket.sendall(sentence.encode("utf-8"))
        
        pbar.set_description(f"Chunk {index+1:02d} (Receiving 0KB)")
        pbar.refresh()

        end_marker_received = False
        while not stop_processing_event.is_set():
            try:
                data = client_socket.recv(8192)
            except socket.timeout:
                if stop_processing_event.is_set():
                    tqdm.write(f"DEBUG: Chunk {index+1:02d} recv timed out during shutdown.")
                    break
                tqdm.write(f"WARNING: Chunk {index+1:02d} recv timed out (no data for {SOCKET_TIMEOUT}s). Assuming end of chunk data for this attempt.")
                break 
            
            if b"END" in data:
                end_idx = data.find(b"END")
                audio_data_bytes.extend(data[:end_idx])
                current_received_byte_count += end_idx
                end_marker_received = True
                break 

            if not data: 
                break 
            
            audio_data_bytes.extend(data)
            current_received_byte_count += len(data)
            pbar.set_description(f"Chunk {index+1:02d} (Receiving {current_received_byte_count/1024:.0f}KB)")
            pbar.refresh()

        if stop_processing_event.is_set():
            raw_audio_queue.put((index, None))
            return 

        audio_array = np.array([], dtype=np.float32)
        if audio_data_bytes:
            if len(audio_data_bytes) % FLOAT_SIZE != 0:
                tqdm.write(f"WARNING: Chunk {index+1:02d} received data length ({len(audio_data_bytes)}) not a multiple of {FLOAT_SIZE}. Truncating.")
                valid_len = (len(audio_data_bytes) // FLOAT_SIZE) * FLOAT_SIZE
                if valid_len > 0:
                    audio_array = np.frombuffer(audio_data_bytes[:valid_len], dtype=np.float32)
            else:
                audio_array = np.frombuffer(audio_data_bytes, dtype=np.float32)
            
            max_val_str = f"{np.max(audio_array):.3f}" if audio_array.size > 0 else "N/A"
            min_val_str = f"{np.min(audio_array):.3f}" if audio_array.size > 0 else "N/A"
            tqdm.write(f"INFO: Chunk {index+1:02d} processed. Bytes: {len(audio_data_bytes)}, Samples: {audio_array.size}, Max: {max_val_str}, Min: {min_val_str}")
        
        if audio_array.size == 0 and current_received_byte_count > 0 and len(audio_data_bytes) < FLOAT_SIZE :
            tqdm.write(f"WARNING: Chunk {index+1:02d} had {len(audio_data_bytes)} bytes, less than a single float. No audio samples.")
        elif audio_array.size == 0 and not end_marker_received and current_received_byte_count == 0:
             tqdm.write(f"WARNING: No audio data effectively received for chunk {index+1}: \"{sentence[:30]}...\"")

        raw_audio_queue.put((index, audio_array if audio_array.size > 0 else None))
        operation_successful = True

    except ConnectionRefusedError:
        if not stop_processing_event.is_set():
            tqdm.write(f"ERROR: Connection refused for chunk {index+1}. Server {server_ip}:{server_port} unavailable.")
        raw_audio_queue.put((index, None))
    except socket.timeout: 
        if not stop_processing_event.is_set():
            tqdm.write(f"ERROR: Connection timed out for chunk {index+1} to {server_ip}:{server_port}.")
        raw_audio_queue.put((index, None))
    except ValueError as ve:
        if not stop_processing_event.is_set():
            tqdm.write(f"ERROR: ValueError during data processing for chunk {index+1} (\"{sentence[:30]}...\"): {ve}")
        raw_audio_queue.put((index, None))
    except Exception as e:
        if not stop_processing_event.is_set():
            tqdm.write(f"ERROR: Unhandled Exception in fetch_sentence_audio_data for chunk {index+1} (\"{sentence[:30]}...\"): {type(e).__name__}: {e}")
        raw_audio_queue.put((index, None))
    finally:
        if client_socket:
            with active_sockets_lock:
                if client_socket in active_sockets:
                    active_sockets.remove(client_socket)
            try: client_socket.shutdown(socket.SHUT_RDWR)
            except OSError: pass 
            client_socket.close()
        
        if pbar: 
            if stop_processing_event.is_set():
                if not final_desc_set:
                    pbar.set_description(f"Chunk {index+1:02d} (Cancelled)")
                    pbar.colour = 'yellow'
                    final_desc_set = True
            elif operation_successful:
                if not final_desc_set:
                    pbar.set_description(f"Chunk {index+1:02d} (Received {current_received_byte_count/1024:.0f}KB)")
                    pbar.colour = 'green'
                    final_desc_set = True
            else: 
                if not final_desc_set:
                    current_desc_text = pbar.desc
                    if "Failed" not in current_desc_text and "Error" not in current_desc_text and "Timeout" not in current_desc_text:
                        pbar.set_description(f"Chunk {index+1:02d} (Fetch Error)")
                    if pbar.colour not in ['red', 'yellow']: 
                        pbar.colour = 'red'
                    final_desc_set = True
            
            if pbar.n < pbar.total:
                pbar.update(pbar.total - pbar.n)
            if hasattr(pbar, 'refresh') and callable(pbar.refresh): # Check if refresh exists and is callable
                 pbar.refresh()


def audio_processing_and_mixing_thread():
    # ... (No changes from previous version needed for this issue)
    global playback_audio_buffer, next_expected_chunk_index, pending_chunks_map, total_sentence_count
    processed_chunk_count = 0
    while processed_chunk_count < total_sentence_count and not stop_processing_event.is_set():
        try:
            index, audio_chunk_data = raw_audio_queue.get(timeout=0.1)
            if stop_processing_event.is_set(): break
            if audio_chunk_data is None or audio_chunk_data.size == 0 : 
                pending_chunks_map[index] = None
            else:
                pending_chunks_map[index] = audio_chunk_data
        except queue.Empty:
            if all_fetch_threads_done_event.is_set() and \
               (next_expected_chunk_index >= total_sentence_count or \
                (next_expected_chunk_index in pending_chunks_map and pending_chunks_map[next_expected_chunk_index] is None and next_expected_chunk_index +1 >= total_sentence_count) ):
                break
            continue 
        while next_expected_chunk_index in pending_chunks_map:
            if stop_processing_event.is_set(): break
            current_chunk_to_process = pending_chunks_map.pop(next_expected_chunk_index)
            if current_chunk_to_process is not None and current_chunk_to_process.size > 0: 
                with audio_buffer_lock:
                    if stop_processing_event.is_set(): break
                    if playback_audio_buffer.size > overlap_samples and current_chunk_to_process.size > overlap_samples:
                        tail_of_previous_buffer = playback_audio_buffer[-overlap_samples:]
                        head_of_current_chunk = current_chunk_to_process[:overlap_samples]
                        mixed_part = tail_of_previous_buffer * fade_out_curve + head_of_current_chunk * fade_in_curve
                        playback_audio_buffer = np.concatenate((
                            playback_audio_buffer[:-overlap_samples], mixed_part, current_chunk_to_process[overlap_samples:]))
                    else:
                        playback_audio_buffer = np.concatenate((playback_audio_buffer, current_chunk_to_process))
            next_expected_chunk_index += 1
            processed_chunk_count += 1
        if stop_processing_event.is_set(): break
    if not stop_processing_event.is_set() and processed_chunk_count < total_sentence_count:
        pass


def audio_playback_callback(outdata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags):
    # ... (No changes from previous version needed for this issue)
    global current_playback_position, playback_audio_buffer
    if status:
        tqdm.write(f"WARNING: Audio callback status: {status}", file=sys.stderr)
    if stop_processing_event.is_set():
        outdata.fill(0)
        raise sd.CallbackStop
    with audio_buffer_lock:
        remaining_samples_in_buffer = playback_audio_buffer.size - current_playback_position
        samples_to_write_this_callback = min(frames, remaining_samples_in_buffer)
        if samples_to_write_this_callback > 0:
            chunk_to_play_now = playback_audio_buffer[current_playback_position : current_playback_position + samples_to_write_this_callback]
            outdata[:samples_to_write_this_callback, 0] = chunk_to_play_now
            current_playback_position += samples_to_write_this_callback
        if samples_to_write_this_callback < frames:
            outdata[samples_to_write_this_callback:, 0] = 0.0
        all_chunks_processed_or_failed = (next_expected_chunk_index >= total_sentence_count)
        all_processing_done = all_fetch_threads_done_event.is_set() and \
                              raw_audio_queue.empty() and \
                              not pending_chunks_map and \
                              all_chunks_processed_or_failed
        buffer_is_empty_at_playback_head = (current_playback_position >= playback_audio_buffer.size)
        if all_processing_done and buffer_is_empty_at_playback_head:
            outdata[samples_to_write_this_callback:, 0] = 0.0
            raise sd.CallbackStop


def audio_stream_finished_callback():
    playback_finished_event.set()


def cleanup_resources(): 
    global was_interrupted_by_user, final_bar_cleanup_done, final_bar_cleanup_lock

    with final_bar_cleanup_lock: # Ensure this section runs only once
        if final_bar_cleanup_done:
            return # Already cleaned up bars
        
        if not stop_processing_event.is_set():
            stop_processing_event.set()

        # Stop threads and streams first
        global audio_output_stream_ref
        if audio_output_stream_ref and not audio_output_stream_ref.closed:
            try:
                audio_output_stream_ref.stop()
                audio_output_stream_ref.close()
            except Exception: pass 

        global audio_processor_thread_ref, fetcher_threads_ref
        if audio_processor_thread_ref and audio_processor_thread_ref.is_alive():
            audio_processor_thread_ref.join(timeout=THREAD_JOIN_TIMEOUT)

        for t_fetch in fetcher_threads_ref:
            if t_fetch.is_alive():
                t_fetch.join(timeout=THREAD_JOIN_TIMEOUT)
        
        # Now close sockets
        with active_sockets_lock:
            for sock in active_sockets:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
                try: sock.close()
                except OSError: pass
            active_sockets.clear()
    
        # Finally, close the progress bars
        # This sleep helps if threads were just joined and might have done a last refresh
        time.sleep(0.1) 
        for pbar_idx, pbar in enumerate(progress_bars):
            # Check if pbar instance is still valid and not disabled (already closed by tqdm)
            if pbar and hasattr(pbar, 'disable') and not pbar.disable:
                try:
                    # Ensure bar reflects final state if interrupted or error
                    if pbar.n < pbar.total: # If bar didn't reach 100%
                        current_desc = pbar.desc or f"Chunk {pbar_idx+1:02d}"
                        base_desc = current_desc.split('(')[0].strip()
                        color_not_error = pbar.colour not in ['red', 'yellow', 'magenta']

                        # Update description and color based on interruption or error
                        if was_interrupted_by_user and "Cancelled" not in current_desc and "Interrupted" not in current_desc and color_not_error :
                            pbar.set_description(f"{base_desc} (Interrupted)")
                            pbar.colour = 'magenta'
                        # Check if stop_processing_event was set due to other reasons (not direct user Ctrl+C)
                        elif stop_processing_event.is_set() and not was_interrupted_by_user and "Stopped" not in current_desc and color_not_error:
                            pbar.set_description(f"{base_desc} (Stopped)")
                            pbar.colour = 'yellow'
                        
                        pbar.update(pbar.total - pbar.n) # Fill the bar to 100%
                    
                    if hasattr(pbar, 'refresh') and callable(pbar.refresh): pbar.refresh()
                    pbar.close() # Close the bar
                except Exception: pass # Ignore errors during final pbar cleanup
        progress_bars.clear()
        final_bar_cleanup_done = True # Mark that this critical section is done

    # This newline should be printed after all bars are truly closed and gone
    # It might be better placed in the __main__ finally block
    # sys.stdout.write("\n")
    # sys.stdout.flush()


def main():
    global progress_bars, total_sentence_count, DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT
    global audio_processor_thread_ref, fetcher_threads_ref, audio_output_stream_ref
    global was_interrupted_by_user

    main_tasks_completed_normally = False
    overall_start_time = None # Initialize

    parser = argparse.ArgumentParser(description="Enhanced F5TTS client with progress bars and crossfade.")
    # ... (argparse setup)
    parser.add_argument("text_or_path", help="Raw text to synthesize or path to a text file.")
    parser.add_argument("-f", "--file", action="store_true", help="Interpret text_or_path as a file path.")
    parser.add_argument("--ip", type=str, default=DEFAULT_SERVER_IP, help=f"IP address of the F5TTS server (default: {DEFAULT_SERVER_IP})")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT, help=f"Port of the F5TTS server (default: {DEFAULT_SERVER_PORT})")
    args = parser.parse_args()


    server_ip = args.ip
    server_port = args.port

    if args.file:
        if not os.path.isfile(args.text_or_path):
            tqdm.write(f"ERROR: File not found: {args.text_or_path}") # Use tqdm.write if before bars
            sys.exit(1)
        try:
            with open(args.text_or_path, "r", encoding="utf-8") as f:
                full_text_to_synthesize = f.read()
        except Exception as e:
            tqdm.write(f"ERROR: Could not read file {args.text_or_path}: {e}")
            sys.exit(1)
    else:
        full_text_to_synthesize = args.text_or_path


    sentences = split_text_into_sentences(full_text_to_synthesize)
    if not sentences or (len(sentences) == 1 and not sentences[0].strip()):
        tqdm.write("WARNING: Input text is empty or contains no valid sentences after splitting.")
        sys.exit(0)

    total_sentence_count = len(sentences)
    tqdm.write(f"INFO: {total_sentence_count} sentence(s) detected. Initializing...")
    
    # Create bars before any other major output that might interfere
    for i in range(total_sentence_count):
        bar = tqdm(total=1, desc=f"Chunk {i+1:02d} (Waiting)", position=i, leave=True, ncols=100, 
                   bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]',
                   mininterval=0.1, maxinterval=1.0) 
        progress_bars.append(bar)
    # Print a newline after all bars are created so subsequent tqdm.write is below them
    if total_sentence_count > 0: sys.stdout.write("\n") 


    audio_processor_thread_ref = threading.Thread(target=audio_processing_and_mixing_thread, daemon=True)
    audio_processor_thread_ref.start()
    
    tqdm.write(f"INFO: Starting audio playback and chunk fetching from {server_ip}:{server_port}...")
    try:
        audio_output_stream_ref = sd.OutputStream(
            samplerate=SAMPLE_RATE, channels=1,
            callback=audio_playback_callback,
            finished_callback=audio_stream_finished_callback,
            blocksize=1024 
        )
        audio_output_stream_ref.start()
    except Exception as e:
        tqdm.write(f"ERROR: Could not initialize audio output stream: {e}")
        stop_processing_event.set() 
        raise 

    overall_start_time = time.time()
    
    for i, sentence_text in enumerate(sentences):
        if stop_processing_event.is_set(): break 
        fetch_thread = threading.Thread(
            target=fetch_sentence_audio_data,
            args=(sentence_text, progress_bars[i], i, server_ip, server_port),
            daemon=True 
        )
        fetcher_threads_ref.append(fetch_thread)
        fetch_thread.start()

    all_threads_joined_normally = True
    try:
        for t in fetcher_threads_ref:
            while t.is_alive():
                if stop_processing_event.is_set():
                    all_threads_joined_normally = False; break
                t.join(timeout=0.1)
            if not all_threads_joined_normally: break
        
        if all_threads_joined_normally:
            all_fetch_threads_done_event.set()

        if audio_processor_thread_ref.is_alive():
            while audio_processor_thread_ref.is_alive():
                if stop_processing_event.is_set():
                    all_threads_joined_normally = False; break
                audio_processor_thread_ref.join(timeout=0.1)

        if not playback_finished_event.is_set() and all_threads_joined_normally:
            while not playback_finished_event.is_set():
                if stop_processing_event.is_set():
                    all_threads_joined_normally = False; break
                playback_finished_event.wait(timeout=0.1)
        
        if all_threads_joined_normally and playback_finished_event.is_set():
            main_tasks_completed_normally = True

    except Exception as e: 
        tqdm.write(f"ERROR: Unexpected error in main operational loop: {type(e).__name__} {e}")
        stop_processing_event.set() 
    
    # End of main operational part.
    # Status messages will be printed after this, then final cleanup.

    # A brief pause to let threads finish their last tqdm.write or pbar.refresh() calls
    # before we print the summary status.
    time.sleep(0.2) 

    if was_interrupted_by_user:
        tqdm.write("INFO: Program terminated due to user interruption.")
    elif main_tasks_completed_normally:
        all_chunks_successful = True
        for pbar in progress_bars:
            # Check pbar exists and has 'colour' attribute before accessing
            if pbar and hasattr(pbar, 'colour') and pbar.colour != 'green': 
                all_chunks_successful = False
                break
        if all_chunks_successful:
             tqdm.write(f"SUCCESS: All operations completed in {time.time() - overall_start_time:.2f} seconds.")
        else:
             tqdm.write(f"WARNING: Operations completed with some errors in {time.time() - overall_start_time:.2f} seconds. Check logs.")
    else: 
        tqdm.write("INFO: Program terminated with an incomplete or error state.")
    
    # Another small delay before the absolute final cleanup in __main__'s finally block.
    # This helps ensure the above tqdm.write messages are flushed.
    time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        was_interrupted_by_user = True 
        # tqdm.write is safer here if bars are active
        tqdm.write("\nWARNING: User interruption (Ctrl+C) detected. Initiating shutdown...") 
        if not stop_processing_event.is_set():
            stop_processing_event.set()
    except Exception as e: 
        tqdm.write(f"\nCRITICAL ERROR: An error occurred in main: {type(e).__name__}: {e}")
        # import traceback 
        # traceback.print_exc()
        if not stop_processing_event.is_set():
            stop_processing_event.set()
    finally:
        # This cleanup_resources call is the one that should definitively close bars.
        cleanup_resources() 
        # Any final messages after absolutely everything is done.
        # But usually, the messages in main() or the KeyboardInterrupt handler are sufficient.
        sys.stdout.write("\n") # Final newline to ensure prompt is clean
        sys.stdout.flush()
        # print("INFO: Program exit.")