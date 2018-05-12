from __future__ import print_function

import os
import sys

sys.path.insert(0, os.path.realpath(__file__ + ('/..' * 2)))
print(f'Running from package root directory {sys.path[0]}')

import argparse

from common.discriminators import *
import PIL.Image as Image
import torch.optim as optim
import torch.utils.data
import torchvision.datasets as datasets
import torchvision.transforms as transforms
from train_loop import TrainLoop

# Training settings
from common.generators import Generator

parser = argparse.ArgumentParser(description='Hyper volume training of GANs')
parser.add_argument('--batch-size', type=int, default=64, metavar='N', help='input batch size for training (default: 64)')
parser.add_argument('--epochs', type=int, default=50, metavar='N', help='number of epochs to train (default: 50)')
parser.add_argument('--lr', type=float, default=0.0002, metavar='LR', help='learning rate (default: 0.0002)')
parser.add_argument('--beta1', type=float, default=0.5, metavar='lambda', help='Adam beta param (default: 0.5)')
parser.add_argument('--beta2', type=float, default=0.999, metavar='lambda', help='Adam beta param (default: 0.999)')
parser.add_argument('--ndiscriminators', type=int, default=8, help='Number of discriminators. Default=8')
parser.add_argument('--checkpoint-epoch', type=int, default=None, metavar='N', help='epoch to load for checkpointing. If None, training starts from scratch')
parser.add_argument('--checkpoint-path', type=str, default=None, metavar='Path', help='Path for checkpointing')
parser.add_argument('--data-path', type=str, default='./celebA', metavar='Path', help='Path to data')
parser.add_argument('--workers', type=int, help='number of data loading workers', default=4)
parser.add_argument('--seed', type=int, default=1, metavar='S', help='random seed (default: 1)')
parser.add_argument('--save-every', type=int, default=3, metavar='N', help='how many epochs to wait before logging training status. Default is 3')
parser.add_argument('--train-mode', choices=['vanilla', 'hyper', 'gman', 'gman_grad', 'loss_delta', 'mgd'], default='vanilla', help='Salect train mode. Default is vanilla (simple average of Ds losses)')
parser.add_argument('--disc-mode', choices=['RP', 'MD'], default='RP', help='Multiple identical Ds with random projections (RP) or Multiple distinct Ds without projection (MD)')
parser.add_argument('--nadir-slack', type=float, default=1.5, metavar='nadir', help='factor for nadir-point update. Only used in hyper mode (default: 1.5)')
parser.add_argument('--alpha', type=float, default=0.8, metavar='alhpa', help='Used in GMAN and loss_del modes (default: 0.8)')
parser.add_argument('--no-cuda', action='store_true', default=False, help='Disables GPU use')
args = parser.parse_args()
args.cuda = True if not args.no_cuda and torch.cuda.is_available() else False

torch.manual_seed(args.seed)
if args.cuda:
	torch.cuda.manual_seed(args.seed)

transform = transforms.Compose([transforms.Resize((64, 64), interpolation=Image.BICUBIC), transforms.RandomHorizontalFlip(), transforms.ToTensor(), transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])

celebA_data = datasets.ImageFolder(args.data_path, transform=transform)

train_loader = torch.utils.data.DataLoader(celebA_data, batch_size=args.batch_size, shuffle=True, num_workers=args.workers)

generator = Generator(100, [1024, 512, 256, 128], 3).train()

if args.disc_mode == 'RP':
	disc_list = []
	for i in range(args.ndiscriminators):
		disc = Discriminator(3, [128, 256, 512, 1024], 1, optim.Adam, args.lr, (args.beta1, args.beta2)).train()
		disc_list.append(disc)

elif args.disc_mode == 'MD':
	D1 = Discriminator_vanilla(ndf=64, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()
	D2 = Discriminator_f6(ndf=64, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()
	D3 = Discriminator_f8(ndf=32, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()
	D4 = Discriminator_f4s3(ndf=64, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()
	D5 = Discriminator_dense(ndf=64, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()
	D6 = Discriminator_f16(ndf=16, nc=3, optimizer=optim.Adam, lr=args.lr, betas=(args.beta1, args.beta2)).train()

	disc_list = [D1, D2, D3, D4, D5, D6][:min(args.ndiscriminators, 6)]

if args.cuda:
	generator = generator.cuda()
	for disc in disc_list:
		disc = disc.cuda()
	torch.backends.cudnn.benchmark=True

optimizer = optim.Adam(generator.parameters(), lr=args.lr, betas=(args.beta1, args.beta2))

trainer = TrainLoop(generator, disc_list, optimizer, train_loader, nadir_slack=args.nadir_slack, alpha=args.alpha, train_mode=args.train_mode, checkpoint_path=args.checkpoint_path, checkpoint_epoch=args.checkpoint_epoch, cuda=args.cuda)

print('Cuda Mode is: {}'.format(args.cuda))
print('Train Mode is: {} - {}'.format(args.train_mode, args.disc_mode))
print('Number of discriminators is: {}'.format(len(disc_list)))

trainer.train(n_epochs=args.epochs, save_every=args.save_every)
