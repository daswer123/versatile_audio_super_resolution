#!/usr/bin/python3
import os
import torch
import logging
from audiosr import super_resolution, build_model, save_wave, get_time, read_list
import argparse

os.environ["TOKENIZERS_PARALLELISM"] = "true"
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.WARNING)

parser = argparse.ArgumentParser()

parser.add_argument(
    "-i",
    "--input_audio_file",
    type=str,
    required=False,
    help="Input audio file for audio super resolution",
)

parser.add_argument(
    "-il",
    "--input_file_list",
    type=str,
    required=False,
    default="",
    help="A file that contains all audio files that need to perform audio super resolution",
)

parser.add_argument(
    "-s",
    "--save_path",
    type=str,
    required=False,
    help="The path to save model output",
    default="./output",
)

parser.add_argument(
    "--model_name",
    type=str,
    required=False,
    help="The checkpoint you gonna use",
    default="basic",
    choices=["basic","speech"]
)

parser.add_argument(
    "-d",
    "--device",
    type=str,
    required=False,
    help="The device for computation. If not specified, the script will automatically choose the device based on your environment.",
    default="auto",
)

parser.add_argument(
    "--ddim_steps",
    type=int,
    required=False,
    default=50,
    help="The sampling step for DDIM",
)

parser.add_argument(
    "-gs",
    "--guidance_scale",
    type=float,
    required=False,
    default=3.5,
    help="Guidance scale (Large => better quality and relavancy to text; Small => better diversity)",
)

parser.add_argument(
    "--seed",
    type=int,
    required=False,
    default=42,
    help="Change this value (any integer number) will lead to a different generation result.",
)

args = parser.parse_args()
torch.set_float32_matmul_precision("high")
save_path = os.path.join(args.save_path, get_time())

assert args.input_file_list is not None or args.input_audio_file is not None,"Please provide either a list of audio files or a single audio file"

input_file = args.input_audio_file
random_seed = args.seed
sample_rate=48000
latent_t_per_second=12.8
guidance_scale = args.guidance_scale

os.makedirs(save_path, exist_ok=True)
audiosr = build_model(model_name=args.model_name, device=args.device)


def split_into_chunks(audio, chunk_length_ms=45000):
    """
    Разбивает аудио на кусочки длиной chunk_length_ms миллисекунд.
    """
    chunks = []
    while len(audio) > chunk_length_ms:
        chunks.append(audio[:chunk_length_ms])
        audio = audio[chunk_length_ms:]

    chunks.append(audio)
    return chunks

if(args.input_file_list):
    print("Generate audio based on the text prompts in %s" % args.input_file_list)
    files_todo = read_list(args.input_file_list)
else: 
    files_todo = [input_file]
    
for input_file in files_todo:
    name = os.path.basename(input_file).split(".")[0]+"_AudioSR_Processed_48K"

#     waveform = super_resolution(
#         audiosr,
#         input_file,
#         seed=random_seed,
#         guidance_scale=guidance_scale,
#         ddim_steps=args.ddim_steps,
#         latent_t_per_second=latent_t_per_second
#     )
#     save_wave(waveform, save_path, name=name, samplerate=sample_rate)


from pydub import AudioSegment

def process_files(files_todo, temp_dir='temp_files'):
    os.makedirs(temp_dir, exist_ok=True)

    for input_file in files_todo:
        name = os.path.basename(input_file).split(".")[0]
        audio = AudioSegment.from_file(input_file)

        # Разбить на кусочки по 5 секунд
        chunks = split_into_chunks(audio)

        processed_chunks = []
        for i, chunk in enumerate(chunks):
            # Сохраняем временный файл
            temp_name = f"{temp_dir}/temp_{name}_{i}.wav"
            chunk.export(temp_name, format="wav")
            
            # Запускаем обработку
            waveform = super_resolution(
                audiosr,
                temp_name,
                seed=random_seed,
                guidance_scale=guidance_scale,
                ddim_steps=args.ddim_steps,
                latent_t_per_second=latent_t_per_second
            )

            # Сохраняем обработанный кусочек
            processed_name = f"{name}_AudioSR_Processed_48K_{i}"
            save_wave(waveform, save_path, name=processed_name, samplerate=sample_rate)
            
            # Загружаем обработанный кусочек обратно
            processed_chunk = AudioSegment.from_wav(f"{save_path}/{processed_name}.wav")
            processed_chunks.append(processed_chunk)

            # Удаляем временный файл
            os.remove(temp_name)

        # Собрать все кусочки обратно в один файл используя перекрестное затухание
        processed_audio = processed_chunks[0]
        for chunk in processed_chunks[1:]:
            processed_audio = processed_audio.append(chunk, crossfade=10)

        # Сохранить обработанный аудиофайл
        processed_audio.export(f"{save_path}/{name}_processed.mp3", format='mp3', bitrate="320k")
        processed_audio.export(f"{save_path}/{name}_processed.wav", format='wav')



process_files(files_todo)