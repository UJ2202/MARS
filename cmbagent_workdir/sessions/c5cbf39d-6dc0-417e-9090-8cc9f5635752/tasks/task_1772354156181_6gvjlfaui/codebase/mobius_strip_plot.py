# filename: codebase/mobius_strip_plot.py
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
import os
from datetime import datetime


def plot_mobius_strip(save_dir="data/"):
    """
    Generates and saves a 3D plot of a Möbius strip.

    Parameters
    ----------
    save_dir : str
        Directory where the plot will be saved.

    Returns
    -------
    str
        Path to the saved plot file.
    """
    rcParams['text.usetex'] = False
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "mobius_strip_1_" + timestamp + ".png"
    filepath = os.path.join(save_dir, filename)

    n_theta = 200
    n_w = 50
    theta = np.linspace(0, 2 * np.pi, n_theta)
    w = np.linspace(-1, 1, n_w)
    theta, w = np.meshgrid(theta, w)

    R = 1.0
    width = 0.3

    X = (R + width * w * np.cos(theta / 2.0)) * np.cos(theta)
    Y = (R + width * w * np.cos(theta / 2.0)) * np.sin(theta)
    Z = width * w * np.sin(theta / 2.0)

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(X, Y, Z, cmap="viridis", edgecolor="none", alpha=0.95, antialiased=True)
    ax.set_title("3D Möbius Strip")
    ax.set_xlabel("X (length units)")
    ax.set_ylabel("Y (length units)")
    ax.set_zlabel("Z (length units)")
    ax.grid(True)
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label="Surface value (arbitrary units)")
    plt.tight_layout()
    plt.savefig(filepath, dpi=300)
    plt.close(fig)
    print("3D Möbius strip plot saved to " + filepath)
    print("The plot shows a Möbius strip in 3D with axes labeled in length units.")
    return filepath


plot_mobius_strip()