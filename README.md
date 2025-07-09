# GoodStudent

Goodstudent aim at creating an pedagogic tool to help mastering his courses through learning by teaching methodes using an Intelligent agent to improve learning condition.

#Requirements :
Enshure you have Anaconda and Cuda compatibility

1. Unity project (base)
2. vosk-model-en-us-0.22 (STT model)
   - https://alphacephei.com/vosk/models
     Put the model in : GoodStudent>Assets>StreamingAssets
3. Ollama (with gemma3:4b in serve mod)
   - https://ollama.com
   - $ollama run gemma3:4b
4. F5-TTS
  - https://github.com/SWivid/F5-TTS
  and add/replace the files that are stored in GoodStudent>ExternalRessources>F5TTS in F5TTS>src>f5_tts

5. create a conda env with
   - conda env create -f env_f5tts.yaml
     (env_f5tts.yaml is stored in GoodStudent>ExternalRessources>Conda)
6. Start env_f5tts and use "uvicorn tts_api_server:app --host 0.0.0.0 --port 8000" in F5TTS>src>f5_tts>fast_API
7. Start another env_f5tts and use "python [path]\F5-TTS\src\f5_tts\socket_server.py
8. Start Ollama (gemma3:4b) in serve mod
   - $ollama serve

