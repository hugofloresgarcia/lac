from pathlib import Path

import audiotools as at
import argbind
import tqdm
import shutil

@argbind.bind(without_prefix=True, positional=True)
def split(
    audio_folder: str, 
    output_folder: str,
    test_amt: float = 0.05,
):
    audio_files = at.util.find_audio(audio_folder)

    test_amt = int(len(audio_files) * test_amt)
    train_amt = len(audio_files) - test_amt

    train_files = audio_files[:train_amt]
    test_files = audio_files[train_amt:]

    train_folder = Path(output_folder) / "train"
    test_folder = Path(output_folder) / "test"

    train_folder.mkdir(parents=True, exist_ok=True)
    test_folder.mkdir(parents=True, exist_ok=True)

    print(f"Copying {len(train_files)} files to {train_folder}")
    for file in tqdm.tqdm(train_files):
        shutil.copy(file, train_folder / Path(file).name)

    print(f"Copying {len(test_files)} files to {test_folder}")
    for file in tqdm.tqdm(test_files):
        shutil.copy(file, test_folder / Path(file).name)

    

if __name__ == "__main__":
    args = argbind.parse_args()

    with argbind.scope(args):
        split()