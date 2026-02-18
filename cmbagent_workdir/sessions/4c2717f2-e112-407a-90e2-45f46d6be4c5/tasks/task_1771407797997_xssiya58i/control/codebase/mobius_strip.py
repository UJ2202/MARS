# filename: codebase/mobius_strip.py
import numpy as np
import matplotlib
matplotlib.rcParams['text.usetex'] = False
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
from datetime import datetime


def mobius_strip(R=1.0, w_max=0.2, n_theta=200, n_w=30):
    """
    Generate the 3D coordinates of a Möbius strip.

    Parameters
    ----------
    R : float
        Radius of the center circle of the Möbius strip (units: length).
    w_max : float
        Half-width of the strip (units: length).
    n_theta : int
        Number of points along the circle (theta direction).
    n_w : int
        Number of points along the width (w direction).

    Returns
    -------
    X, Y, Z : ndarray
        2D arrays of shape (n_w, n_theta) with the 3D coordinates of the strip.
    """
    theta = np.linspace(0, 2 * np.pi, n_theta)
    w = np.linspace(-w_max, w_max, n_w)
    theta, w = np.meshgrid(theta, w)
    X = (R + w * np.cos(theta / 2.0)) * np.cos(theta)
    Y = (R + w * np.cos(theta / 2.0)) * np.sin(theta)
    Z = w * np.sin(theta / 2.0)
    return X, Y, Z


def plot_mobius_strip(X, Y, Z, save_path):
    """
    Plot and save a 3D Möbius strip.

    Parameters
    ----------
    X, Y, Z : ndarray
        2D arrays with the 3D coordinates of the strip.
    save_path : str
        Path to save the PNG file.
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(X, Y, Z, rstride=1, cstride=1, color='royalblue', edgecolor='k', linewidth=0.2, alpha=0.9, antialiased=True)
    ax.set_title("3D Möbius Strip", fontsize=16)
    ax.set_xlabel("X (length units)", fontsize=12)
    ax.set_ylabel("Y (length units)", fontsize=12)
    ax.set_zlabel("Z (length units)", fontsize=12)
    ax.grid(True)
    ax.view_init(elev=30, azim=60)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close(fig)
    print("3D Möbius strip plot saved to " + save_path)


if __name__ == "__main__":
    R = 1.0
    w_max = 0.3
    n_theta = 400
    n_w = 60
    X, Y, Z = mobius_strip(R=R, w_max=w_max, n_theta=n_theta, n_w=n_w)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_name = "mobius_strip_1_" + timestamp + ".png"
    save_dir = "data"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, plot_name)
    plot_mobius_strip(X, Y, Z, save_path)
    print("The Möbius strip is parametrized with center radius R = " + str(R) + " and half-width w_max = " + str(w_max) + " (all units arbitrary).")