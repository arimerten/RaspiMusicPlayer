"""
Laptop simulator: shows the screen in a window, scaled up so it's easy to see.

Run from the project folder:
  .venv\\Scripts\\python desktop.py

The keys stand in for the Pi's rotary knob:
  Up / Down or mouse wheel   turn the knob
  Enter or Space             press the knob
  Backspace or Left          hold the knob (back)
  Esc                        quit
"""

import tkinter as tk

from PIL import Image, ImageTk

from app import App
from screens import HEIGHT, WIDTH

SCALE = 2  # window is 2x the real screen size


class Simulator:
    def __init__(self, root):
        self.root = root
        self.app = App()

        root.title("RaspiMusicPlayer simulator")
        root.configure(bg="#202020")
        self.screen = tk.Label(root, bd=0)
        self.screen.pack(padx=20, pady=(20, 8))
        tk.Label(
            root,
            text="Knob: Up/Down or wheel = turn   Enter = press   Backspace = hold (back)   Esc: quit",
            bg="#202020",
            fg="#aaaaaa",
        ).pack(pady=(0, 12))

        root.bind("<Up>", lambda e: self.control(self.app.turn, -1))
        root.bind("<Down>", lambda e: self.control(self.app.turn, 1))
        root.bind("<MouseWheel>", lambda e: self.control(self.app.turn, -1 if e.delta > 0 else 1))
        root.bind("<Return>", lambda e: self.control(self.app.press))
        root.bind("<space>", lambda e: self.control(self.app.press))
        root.bind("<BackSpace>", lambda e: self.control(self.app.back))
        root.bind("<Left>", lambda e: self.control(self.app.back))
        root.bind("<Escape>", lambda e: root.destroy())

        self.redraw()
        self.root.after(1000, self.tick)

    def control(self, action, *args):
        action(*args)
        self.redraw()

    def tick(self):
        self.app.tick()
        self.redraw()  # always redraw so the clock stays current
        self.root.after(1000, self.tick)

    def redraw(self):
        frame = self.app.render()
        big = frame.resize((WIDTH * SCALE, HEIGHT * SCALE), Image.NEAREST)
        self.photo = ImageTk.PhotoImage(big)  # keep a reference so Tk doesn't drop it
        self.screen.configure(image=self.photo)


if __name__ == "__main__":
    root = tk.Tk()
    Simulator(root)
    root.mainloop()
