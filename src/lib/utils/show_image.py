import matplotlib.pyplot as plt


def show_image(transforms, data):
    for i in range(9):
        plt.subplot(3, 3, i + 1)
        plt.imshow(transforms(data.data[i]))

    plt.show()
