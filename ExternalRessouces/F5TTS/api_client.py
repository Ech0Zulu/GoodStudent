import socket
import sys
import argparse
import os
import time
import numpy as np
import sounddevice as sd
import re

server_ip = "127.0.0.1"
server_port = 9998
sample_rate = 24000  # F5-TTS default

def sentence_split(text):
    # Découpe basique par ponctuation, propre pour du français
    return re.split(r'(?<=[.?!])\s+', text.strip())

def play_audio(wav_data):
    # Convertit les données binaires en float32, puis joue
    audio_array = np.frombuffer(wav_data, dtype=np.float32)
    sd.play(audio_array, samplerate=sample_rate)
    sd.wait()

def stream_sentence(sentence):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((server_ip, server_port))
            s.sendall(sentence.encode("utf-8"))

            audio_data = bytearray()
            while True:
                data = s.recv(8192)
                if not data:
                    break
                if data == b"END":
                    break
                audio_data.extend(data)
            return bytes(audio_data)

    except Exception as e:
        print(f"❌ Erreur pour la phrase : {sentence}\n{e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text_or_path", help="Texte brut ou chemin vers un fichier")
    parser.add_argument("-f", "--file", action="store_true", help="Lire le texte depuis un fichier")
    args = parser.parse_args()

    # Lire texte
    if args.file:
        if not os.path.isfile(args.text_or_path):
            print(f"❌ Fichier introuvable : {args.text_or_path}")
            sys.exit(1)
        with open(args.text_or_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    else:
        full_text = args.text_or_path

    # Découpe
    phrases = sentence_split(full_text)
    print(f"🧩 {len(phrases)} phrase(s) détectée(s)")

    total_start = time.time()

    for i, phrase in enumerate(phrases):
        print(f"\n🗣️  Phrase {i + 1}/{len(phrases)} : {phrase}")
        t_start = time.time()
        audio = stream_sentence(phrase)
        if audio:
            print(f"🎧 Lecture...")
            play_audio(audio)
            print(f"✅ Fini en {time.time() - t_start:.2f} sec")
        else:
            print("⚠️ Pas de réponse audio")

    print(f"\n✅ Terminé. Durée totale : {time.time() - total_start:.2f} sec")

if __name__ == "__main__":
    main()
