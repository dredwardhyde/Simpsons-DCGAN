from __future__ import print_function, division

import os
os.environ["KERAS_BACKEND"] = "plaidml.keras.backend"

from keras.datasets import mnist
from keras.layers import Input, Dense, Reshape, Flatten, Dropout, Conv2DTranspose
from keras.layers import BatchNormalization, Activation, ZeroPadding2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import UpSampling2D, Conv2D
from keras.models import Sequential, Model
from keras.optimizers import Adam
from keras.initializers import TruncatedNormal

import matplotlib.pyplot as plt
from PIL import Image
from glob import glob

import sys

import numpy as np

class DCGAN():
    def __init__(self):
        # Input shape
        self.img_rows = 128
        self.img_cols = 128
        self.channels = 3
        self.img_shape = (self.img_rows, self.img_cols, self.channels)
        self.latent_dim = 100

        optimizer_generator = Adam(0.0004, 0.5)
        optimizer_discriminator = Adam(0.00004, 0.5)

        # Build and compile the discriminator
        self.discriminator = self.build_discriminator()
        self.discriminator.compile(loss='binary_crossentropy',
            optimizer=optimizer_discriminator,
            metrics=['binary_accuracy'])

        # Build the generator
        self.generator = self.build_generator()

        # The generator takes noise as input and generates imgs
        z = Input(shape=(self.latent_dim,))
        img = self.generator(z)

        # For the combined model we will only train the generator
        #self.discriminator.trainable = False

        # The discriminator takes generated images as input and determines validity
        valid = self.discriminator(img)

        # The combined model  (stacked generator and discriminator)
        # Trains the generator to fool the discriminator
        self.combined = Model(z, valid)
        self.combined.compile(loss='binary_crossentropy', optimizer=optimizer_generator)

    def build_generator(self):

        model = Sequential()

        model.add(Dense(8 * 8 * 1024, activation="relu", input_dim=self.latent_dim))
        model.add(Reshape((8, 8, 1024)))
        model.add(LeakyReLU())

        model.add(Conv2DTranspose(filters=512, kernel_size=[5,5], strides=[2,2], kernel_initializer=TruncatedNormal(stddev=WEIGHT_INIT_STDDEV), padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU())

        model.add(Conv2DTranspose(filters=256, kernel_size=[5,5], strides=[2,2], kernel_initializer=TruncatedNormal(stddev=WEIGHT_INIT_STDDEV), padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU())

        model.add(Conv2DTranspose(filters=128, kernel_size=[5,5], strides=[2,2], kernel_initializer=TruncatedNormal(stddev=WEIGHT_INIT_STDDEV), padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU())

        model.add(Conv2DTranspose(filters=64, kernel_size=[5,5], strides=[2,2], kernel_initializer=TruncatedNormal(stddev=WEIGHT_INIT_STDDEV), padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU())

        model.add(Conv2DTranspose(filters=self.channels, kernel_size=[5,5], kernel_initializer=TruncatedNormal(stddev=WEIGHT_INIT_STDDEV), padding="same"))
        model.add(Activation("tanh"))

        print("Generator")
        model.summary()

        noise = Input(shape=(self.latent_dim,))
        img = model(noise)

        return Model(noise, img)

    def build_discriminator(self):

        model = Sequential()

        model.add(Conv2D(filters=64, kernel_size=[5,5], strides=[2,2], input_shape=self.img_shape, padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU(alpha=0.2))

        model.add(Conv2D(filters=128, kernel_size=[5,5], strides=[2,2], input_shape=self.img_shape, padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU(alpha=0.2))

        model.add(Conv2D(filters=256, kernel_size=[5,5], strides=[2,2], input_shape=self.img_shape, padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU(alpha=0.2))

        model.add(Conv2D(filters=512, kernel_size=[5,5], strides=[1,1], input_shape=self.img_shape, padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU(alpha=0.2))

        model.add(Conv2D(filters=1024, kernel_size=[5,5], strides=[2,2], input_shape=self.img_shape, padding="same"))
        model.add(BatchNormalization(epsilon=EPSILON, trainable=True))
        model.add(LeakyReLU(alpha=0.2))

        model.add(Reshape((-1, 8 * 8 * 1024)))

        model.add(Flatten())
        model.add(Dense(1, activation='sigmoid'))

        print("Discriminator")
        model.summary()

        img = Input(shape=self.img_shape)
        validity = model(img)

        return Model(img, validity)

    def train(self, epochs, batch_size=128, save_interval=50):

        X_train = np.asarray(
            [np.asarray(Image.open(file).resize((self.img_rows, self.img_cols))) for file in glob(INPUT_DATA_DIR + '*')])

        print("Input: " + str(X_train.shape))

        np.random.shuffle(X_train)

        # Rescale -1 to 1
        X_train = X_train / 127.5 - 1.0

        valid = np.ones((batch_size, 1))
        fake = np.zeros((batch_size, 1))

        for epoch in range(epochs):

            # ---------------------
            #  Train Discriminator
            # ---------------------

            # Select a random half of images
            idx = np.random.randint(0, X_train.shape[0], batch_size)
            imgs = X_train[idx]

            # Sample noise and generate a batch of new images
            noise = np.random.uniform(-1, 1, (batch_size, self.latent_dim))
            gen_imgs = self.generator.predict(noise)

            # Train the discriminator (real classified as ones and generated as zeros)
            d_loss_real = self.discriminator.train_on_batch(imgs, valid)
            d_loss_fake = self.discriminator.train_on_batch(gen_imgs, fake)
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            # ---------------------
            #  Train Generator
            # ---------------------

            # Train the generator (wants discriminator to mistake images as real)
            g_loss = self.combined.train_on_batch(noise, valid)

            # Plot the progress
            print ("%d [D loss: %f, acc.: %.2f%%] [G loss: %f]" % (epoch, d_loss[0], 100*d_loss[1], g_loss))

            # If at save interval => save generated image samples
            if epoch % save_interval == 0:
                self.save_imgs(epoch)

    def save_imgs(self, epoch):
        r, c = 5, 5
        noise = np.random.uniform(-1, 1, (r * c, self.latent_dim))
        gen_imgs = self.generator.predict(noise)

        # Rescale images 0 - 1
        gen_imgs = 0.5 * gen_imgs + 0.5

        fig, axs = plt.subplots(r, c)
        cnt = 0
        for i in range(r):
            for j in range(c):
                axs[i,j].imshow(gen_imgs[cnt, :,:,0])
                axs[i,j].axis('off')
                cnt += 1
        fig.savefig("images/simpsons_%d.png" % epoch)
        plt.close()


INPUT_DATA_DIR = "/Users/edwardhyde/PycharmProjects/gan/cropped/"
WEIGHT_INIT_STDDEV = 0.02
EPSILON = 0.00005

dcgan = DCGAN()
dcgan.train(epochs=4000, batch_size=64, save_interval=20)