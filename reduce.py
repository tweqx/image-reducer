import tkinter as tk
import tkinter.messagebox
import tkinter.filedialog
from PIL import Image, ImageTk
import os
import pygubu
import random

class ReducingApp:
    def __init__(self):
        self.filename = None
        self.image = None

        self.phase = None # None, 'x' or 'y'
        self.pixels_done = None
        self.secondary_coords = [None, None]

        self.minimap_image = None
        self.minimap_image_id = None
        self.minimap_size = None
        self.minimap_border_id = None
        self.minimap_region_id = None

        self.grid_x = []
        self.grid_y = []

        self._debouncing_prev_releases = {} # To debounce keystokes

        ## Loading UI
        self.builder = builder = pygubu.Builder()
        builder.add_from_file('reduce.ui')

        self.mainwindow = builder.get_object('window')
        self.filechooser = builder.get_object('filechooser')
        self.remaining = builder.get_object('remaining')
        self.percentage = builder.get_object('percentage')
        self.canvas = c = builder.get_object('canvas')

        builder.connect_callbacks(self)

        # Draw canvas lines
        self.block_count = (25, 63)

        grid_size = 15
        size_x, size_y = self.block_count

        for i in range(size_x + 1):
          c.create_line(5 + grid_size*i, 5, 5 + grid_size*i, 5 + grid_size*size_y)
        for j in range(size_y + 1):
          c.create_line(5, 5 + grid_size*j, 5 + grid_size*size_x, 5 + grid_size*j)

        # Draw canvas pixels
        self.pixels = []
        for i in range(size_x):
          for j in range(size_y):
            p = c.create_rectangle(5 + grid_size*i, 5 + grid_size*j, 5 + grid_size*(i+1), 5 + grid_size*(j+1), fill='')
            self.pixels.append(p)

        # Active region display
        self.minimap_region_id = c.create_rectangle(-1, -1, -1, -1)

    def run(self):
        self.filechooser.folder_button.invoke()
        self.mainwindow.mainloop()

    def load_image(self):
        try:
          self.image = Image.open(self.filename)
        except:
          self.image = None
          return False

        self.phase = 'x'

        # Setup statistics variables
        self.pixels_done = 0
        self.update_statistics()

        # Update canvas
        self.secondary_coords = [
          min(0, (self.image.width // 2) - (self.block_count[0]//2)),
          min(0, (self.image.height // 2) - (self.block_count[0]//2))
        ]

        self.minimap_size = map_size = (int(self.canvas.winfo_width()*0.2), int(self.canvas.winfo_width()*0.2 / self.image.width * self.image.height))
        self.canvas_minimap = map = ImageTk.PhotoImage(self.image.resize(self.minimap_size))

        if self.minimap_image_id != None: self.canvas.delete(self.minimap_image_id)
        self.minimap_image_id = self.canvas.create_image(self.canvas.winfo_width() - map_size[0]/2, map_size[1]/2, image=map)

        if self.minimap_border_id != None: self.canvas.delete(self.minimap_border_id)
        self.minimap_border_id = self.canvas.create_rectangle(self.canvas.winfo_width() - map_size[0], 0, self.canvas.winfo_width(), map_size[1])

        self.update_canvas()

        return True

    def update_statistics(self):
        if self.phase == 'x':
          percent = self.pixels_done/(self.image.width + self.image.height)
        else:
          percent = (self.image.width + self.pixels_done)/(self.image.width + self.image.height)
        self.percentage.configure(text=f"{100*percent:.2f}%")

        phase_count = 1 if self.phase == 'x' else 2
        pixels_todo = self.image.width if self.phase == 'x' else self.image.height
        self.remaining.configure(text=f"{phase_count} of 2 - {self.pixels_done}/{pixels_todo}")

    def update_canvas(self):
        w, h = self.image.size

        if self.phase == 'x':
          x, y = self.pixels_done, self.secondary_coords[1]
        else:
          x, y = self.secondary_coords[0], self.pixels_done

        def to_hex(rgb):
          r, g, b = rgb[0], rgb[1], rgb[2]
          return '#' + hex(r)[2:].rjust(2, '0') + hex(g)[2:].rjust(2, '0') + hex(b)[2:].rjust(2, '0')

        # Update canvas blocks
        c, p, img = self.canvas, self.pixels, self.image
        s_x, s_y = self.block_count
        for i in range(s_x):
          for j in range(s_y):
            id = p[i*s_y + j]

            if self.phase == 'x':
              if x + i < w and y + j < h:
                color = to_hex(img.getpixel((x + i, y + j)))
              else:
                # Transparent color fs the image is too small
                color = ''
            else:
              if x + j < w and y + i < h:
                color = to_hex(img.getpixel((x + j, y + i)))
              else:
                # Transparent color fs the image is too small
                color = ''
            c.itemconfigure(id, fill=color)

        # Update active region
        def to_minimap(x, y):
          a = self.canvas.winfo_width() - self.minimap_size[0]
          b = 0

          a += x * (self.minimap_size[0] / w)
          b += y * (self.minimap_size[1] / h)

          return (a, b)

        if self.phase == 'x':
          c.coords(self.minimap_region_id, (*to_minimap(x, y), *to_minimap(x + s_x, y + s_y)))
        else:
          c.coords(self.minimap_region_id, (*to_minimap(x, y), *to_minimap(x + s_y, y + s_x)))
        c.tag_raise(self.minimap_region_id)

    ## Callbacks
    def on_path_changed(self, event=None):
        new_filename = self.filechooser.cget('path')

        # No change
        if new_filename == self.filename: return

        if self.filename != None:
          answer = tk.messagebox.askyesno(message="Do you want to lose progress?", title="Do you want to lose progress?")
          if answer == 0:
            # Cancel
            self.filechooser.configure(path=self.filename)
            return

        self.filename = new_filename

        success = self.load_image()
        if not success:
          tk.messagebox.showwarning(message="Unable to load the given image.")

          self.filename = None # Prevent the loss of progress message
          self.filechooser.folder_button.invoke()

    # Debouncing functions - modified from https://gist.github.com/vtsatskin/8e3c0c636339b2228138
    def on_key_press(self, event=None):
      if event.keycode in self._debouncing_prev_releases and self._debouncing_prev_releases[event.keycode] != None:
        self.mainwindow.after_cancel(self._debouncing_prev_releases[event.keycode])
        self._debouncing_prev_releases[event.keycode] = None
      else:
        self.on_key(event)
    def on_key_release(self, event=None):
      def local_func(event):
        self._debouncing_prev_releases[event.keycode] = None
      self._debouncing_prev_releases[event.keycode] = self.mainwindow.after(5, local_func, event)

    # Event handler called once per keypress/keyrelease
    def on_key(self, event=None):
        # A number
        if event.char in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
          self.on_number_key(event)

        # Backspace
        if event.keycode == 22:
          self.on_backspace_key(event)

        # Up/Down
        if event.keycode in [111, 116]:
          self.on_updown_key(event)

    def on_updown_key(self, event=None):
        # No image loaded
        if self.image == None: return

        key = 'up' if event.keycode == 111 else 'down'

        if self.phase == 'x':
          c = self.secondary_coords[1]

          if key == 'down':
            if c + 10 >= self.image.height: return
            self.secondary_coords[1] = c + 10
          else:
            if c - 10 < 0: return
            self.secondary_coords[1] = c - 10
        else:
          c = self.secondary_coords[0]

          if key == 'down':
            if c + 10 >= self.image.width: return
            self.secondary_coords[0] = c + 10
          else:
            if c - 10 <= 0: return
            self.secondary_coords[0] = c - 10

        self.update_canvas()

    def on_backspace_key(self, event=None):
        # No image loaded
        if self.image == None: return

        ## Cancelling last action

        if self.phase == 'x':
          # No blocks yet
          if len(self.grid_x) == 0:
            return

          # Blocks
          else:
            undo = self.grid_x.pop()
            self.pixels_done -= undo
        else:
          # Just went from phase x to phase y
          if len(self.grid_y) == 0:
            self.phase = 'x'

            undo = self.grid_x.pop()
            self.pixels_done = self.image.width - undo
          else:
            undo = self.grid_y.pop()
            self.pixels_done -= undo

        self.update_statistics()
        self.update_canvas()

    def on_number_key(self, event=None):
        # No image loaded
        if self.image == None: return

        number = int(event.char)

        # Is there enough pixels remaining?
        pixels_todo = self.image.width if self.phase == 'x' else self.image.height
        if self.pixels_done + number > pixels_todo:
          tk.messagebox.showwarning(message="Not enough pixels remaining")
          return

        ## Ready to add !

        # Updating stats
        self.pixels_done += number
        self.update_statistics()

        # Update canvas
        self.update_canvas()

        # Adding to the grids
        if self.phase == 'x':
          self.grid_x.append(number)
        else:
          self.grid_y.append(number)

        # End of phase?
        if self.pixels_done == pixels_todo:
          if self.phase == 'x':
            self.pixels_done = 0
            self.phase = 'y'
            self.update_statistics()
            self.update_canvas()
          else:
            # Save reduced file
            self.generate_reduced_image()

            # Restart
            self.filechooser.folder_button.invoke()

    def generate_reduced_image(self):
        ## Generating image...
        reduced = Image.new("RGB", (len(self.grid_x), len(self.grid_y)))

        def average_color(x, y, w, h):
          ar = ag = ab = 0

          for i in range(w):
            for j in range(h):
              rgb = self.image.getpixel((x + i, y + j))

              ar += rgb[0]
              ag += rgb[1]
              ab += rgb[2]

          t = w*h
          return (round(ar/t), round(ag/t), round(ab/t))

        x = 0
        rx = 0
        for i in self.grid_x:
          y = 0
          ry = 0
          for j in self.grid_y:
            reduced.putpixel((rx, ry), average_color(x, y, i, j))
            y += j
            ry += 1
          x += i
          rx += 1

        ## Saving reduced image
        file = tk.filedialog.asksaveasfilename(title="Save reduced image...", defaultextension="png")

        # No image selected
        if file == "" or file == None:
          tk.messagebox.showwarning(title="Cannot save image", message="No file given, cannot save the reduced image.")
          return

        reduced.save(file)

        tk.messagebox.showinfo(message=f"Saved reduced image to {os.path.basename(file)}.", title="Saved reduced image")

if __name__ == '__main__':
    app = ReducingApp()
    app.run()
