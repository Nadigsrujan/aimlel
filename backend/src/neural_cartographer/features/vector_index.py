"""Isolated FAISS worker: never import torch in this process."""
import argparse
import json
from pathlib import Path
import uuid
import faiss
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('build', 'query'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('seed', type=int, nargs='?')
    args = parser.parse_args()
    faiss.omp_set_num_threads(1)
    if args.operation == 'build':
        matrix = np.load(args.directory / 'vectors.npy', allow_pickle=False)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        temporary = args.directory / (uuid.uuid4().hex + '.index')
        faiss.write_index(index, str(temporary))
        temporary.replace(args.directory / 'vectors.index')
    else:
        index = faiss.read_index(str(args.directory / 'vectors.index'))
        if args.seed is None or not 0 <= args.seed < index.ntotal:
            parser.error('Seed index outside vector matrix')
        scores, positions = index.search(index.reconstruct(args.seed).reshape(1, -1), index.ntotal)
        print(json.dumps([[int(i), float(score)] for i, score in zip(positions[0], scores[0]) if i >= 0]))


if __name__ == '__main__':
    main()
