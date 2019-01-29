try:
    # Tkinter for Python 2.xx
    import Tkinter as tk
    from tkFont import Font
    from Tkinter import tkMessageBox as messagebox
except ImportError:
    # Tkinter for Python 3.xx
    import tkinter as tk
    from tkinter.font import Font
    from tkinter import messagebox
from PIL import Image, ImageTk
from tkinter import ttk
import numpy as np
import os
from bbq.utility import to_string
from copy import deepcopy

png_directory = os.path.join(os.path.dirname(__file__), ".graphics")


def string_to_component(s, *arg, **kwarg):
    if s == 'W':
        return W(*arg, **kwarg)
    elif s == 'R':
        return R(*arg, **kwarg)
    elif s == 'L':
        return L(*arg, **kwarg)
    elif s == 'J':
        return J(*arg, **kwarg)
    elif s == 'C':
        return C(*arg, **kwarg)


class AutoScrollbar(ttk.Scrollbar):
    """ A scrollbar that hides itself if it's not needed. """
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
            ttk.Scrollbar.set(self, lo, hi)

    def pack(self, **kw):
        raise tk.TclError('Cannot use pack with the widget ' + self.__class__.__name__)

    def place(self, **kw):
        raise tk.TclError('Cannot use place with the widget ' + self.__class__.__name__)


class SnappingCanvas(tk.Canvas):
    def __init__(self, master, grid_unit, netlist_file, **kw):
        
        """ Initialize the ImageFrame """

        self.frame = ttk.Frame()
        self.frame.grid()  # place Canvas widget on the grid
        self.frame.grid(sticky='nswe')  # make frame container sticky
        self.frame.rowconfigure(0, weight=1)  # make canvas expandable
        self.frame.columnconfigure(0, weight=1)

        # Vertical and horizontal scrollbars for canvas
        hbar = AutoScrollbar(self.frame, orient='horizontal')
        vbar = AutoScrollbar(self.frame, orient='vertical')
        hbar.grid(row=1, column=0, sticky='we')
        vbar.grid(row=0, column=1, sticky='ns')

        tk.Canvas.__init__(self, self.frame, bd=0, highlightthickness=0,
            xscrollcommand=hbar.set, yscrollcommand=vbar.set, bg="white")

        self.grid(row=0, column=0, sticky='nswe')
        
        hbar.configure(command=self.__scroll_x)  # bind scrollbars to the canvas
        vbar.configure(command=self.__scroll_y)


        self.netlist_file = netlist_file
        self.grid_unit = int(grid_unit)
        # self.pack(fill=tk.BOTH, expand=1)
        self.focus_set()
        self.bind('r', lambda event: R(self, event))
        self.bind('l', lambda event: L(self, event))
        self.bind('c', lambda event: C(self, event))
        self.bind('j', lambda event: J(self, event))
        self.bind('w', lambda event: W(self, event))
        self.bind('s', self.save)
        self.bind("<Configure>", self.on_resize)
        self.bind('<Delete>', self.delete_selection)
        self.bind('<Control-a>', self.select_all)
        self.bind('<Control-y>', self.ctrl_y)
        self.bind('<Control-z>', self.ctrl_z)
        self.bind('<MouseWheel>', self.wheel)  # zoom for Windows and MacOS, but not Linux
        self.bind('<Button-5>',   self.wheel)  # zoom for Linux, wheel scroll down
        self.bind('<Button-4>',   self.wheel)  # zoom for Linux, wheel scroll up

        # Handle keystrokes in idle mode, because program slows down on a weak computers,
        # when too many key stroke events in the same time
        # self.bind('<Key>', lambda event: self.after_idle(self.__keystroke, event))

        self.elements = []
        self.history = []
        self.history_location = -1
        self.track_changes = False 
        try:
            with open(netlist_file, 'r') as f:
                self.load_netlist(f)
        except FileNotFoundError:
            with open(netlist_file, 'w') as f:
                pass
        self.track_changes = True 
        self.save()


    # def __keystroke(self, event):
    #     """ Scrolling with the keyboard.
    #         Independent from the language of the keyboard, CapsLock, <Ctrl>+<key>, etc. """
    #     if event.state - self.__previous_state == 4:  # means that the Control key is pressed
    #         pass  # do nothing if Control key is pressed
    #     else:
    #         self.__previous_state = event.state  # remember the last keystroke state
    #         # Up, Down, Left, Right keystrokes
    #         if event.keycode in [68, 39, 102]:  # scroll right, keys 'd' or 'Right'
    #             self.__scroll_x('scroll',  1, 'unit', event=event)
    #         elif event.keycode in [65, 37, 100]:  # scroll left, keys 'a' or 'Left'
    #             self.__scroll_x('scroll', -1, 'unit', event=event)
    #         elif event.keycode in [87, 38, 104]:  # scroll up, keys 'w' or 'Up'
    #             self.__scroll_y('scroll', -1, 'unit', event=event)
    #         elif event.keycode in [83, 40, 98]:  # scroll down, keys 's' or 'Down'
    #             self.__scroll_y('scroll',  1, 'unit', event=event)


    def wheel(self, event):
        old_grid_size = self.grid_unit
        scaling = 1.04
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down, smaller
            self.grid_unit /= scaling
        if event.num == 4 or event.delta == 120:  # scroll up, bigger
            self.grid_unit *= scaling
        self.grid_unit = int(self.grid_unit)

        for el in self.elements:
            el.adapt_to_gridsize(old_grid_size)
        self.on_resize()


    def __scroll_x(self, *args, **kwargs):
        """ Scroll canvas horizontally and redraw the image """
        self.xview(*args)  # scroll horizontally
        self.draw_grid()

    def __scroll_y(self, *args, **kwargs):
        """ Scroll canvas vertically and redraw the image """
        self.yview(*args)  # scroll vertically
        self.draw_grid()


    def ctrl_z(self,event):
        if self.history_location > 0:
            self.track_changes = False 
            self.history_location -= 1
            self.load_netlist(self.history[self.history_location].split('\n'))
            self.track_changes = True 

    def ctrl_y(self,event):
        if 0 < self.history_location < len(self.history)-1:
            self.track_changes = False 
            self.history_location += 1
            self.load_netlist(self.history[self.history_location].split('\n'))
            self.track_changes = True 

    def load_netlist(self,lines):
        self.delete_all()
        for el in lines:
            el = el.replace('\n', '')
            el = el.split(";")
            if el[0] in ['C', 'L', 'R', 'J', 'W']:
                string_to_component(el[0], self, auto_place=el)




    def on_resize(self,event = None):
        self.draw_grid(event)
        self.configure_scrollregion()

    def configure_scrollregion(self):
        xs = [el.x_minus for el in self.elements]+[el.x_plus for el in self.elements]
        ys = [el.y_minus for el in self.elements]+[el.y_plus for el in self.elements]
        self.configure(scrollregion = [0,0,max(xs),max(ys)])

    def draw_grid(self, event = None):

        # Draw the grid
        self.delete("grid")
        dx = 1
        dy = 1
        box_canvas = (self.canvasx(0),  # get visible area of the canvas
                      self.canvasy(0),
                      self.canvasx(self.winfo_width()),
                      self.canvasy(self.winfo_height()))

        self.background = self.create_rectangle(
            *box_canvas, fill='white', tags='grid')
        for x in np.arange(int(box_canvas[0]/self.grid_unit)*self.grid_unit, box_canvas[2], self.grid_unit):
            for y in np.arange(int(box_canvas[1]/self.grid_unit)*self.grid_unit, box_canvas[3], self.grid_unit):
                self.create_line(x-dx, y, x+2*dx, y, tags='grid')
                self.create_line(x, y-dy, x, y+2*dy, tags='grid')
        self.tag_lower('grid')
        self.tag_bind('grid', '<ButtonPress-1>', self.start_selection_field)
        self.tag_bind('grid', "<B1-Motion>", self.expand_selection_field)
        self.tag_bind('grid', "<ButtonRelease-1>", self.end_selection_field)
        

    def start_selection_field(self, event):
        self.deselect_all()
        self.selection_rectangle_x_start = event.x
        self.selection_rectangle_y_start = event.y
        self.selection_rectangle = self.create_rectangle(
            event.x, event.y, event.x, event.y, dash=(3, 5))

    def expand_selection_field(self, event):
        self.deselect_all()
        self.coords(self.selection_rectangle,
        min(event.x,self.selection_rectangle_x_start), 
        min(event.y,self.selection_rectangle_y_start), 
        max(event.x,self.selection_rectangle_x_start), 
        max(event.y,self.selection_rectangle_y_start))
        for el in self.elements:
            el.box_select(*self.coords(self.selection_rectangle))

    def end_selection_field(self, event):
        self.delete(self.selection_rectangle)

    def deselect_all(self, event=None):
        for el in self.elements:
            el.deselect()

    def select_all(self, event=None):
        for el in self.elements:
            el.force_select()

    def delete_selection(self, event=None):
        self.track_changes = False
        to_delete = [el for el in self.elements if el.selected]
        for el in to_delete:
            el.delete()
        self.track_changes = True
        self.save()

    def delete_all(self, event=None):
        to_delete = [el for el in self.elements]
        for el in to_delete:
            el.delete()

    def save(self,event = None):

        netlist_string = ""
        for el in self.elements:
            v,l  = el.prop
            if v is None:
                v = ''
            else:
                v = "%e" % v

            if l is None:
                l = ''
                
            netlist_string+=("%s;%s;%s;%s;%s\n" % (
                type(el).__name__,
                el.coords_to_node_string(el.x_minus, el.y_minus),
                el.coords_to_node_string(el.x_plus, el.y_plus),
                v, l))

        with open(self.netlist_file, 'w') as f:
            f.write(netlist_string)

        if self.track_changes:
            del self.history[self.history_location+1:]
            self.history.append(netlist_string)
            self.history_location+=1

        
    def create_circle(self, x, y, r):
        x0 = x - r
        y0 = y - r
        x1 = x + r
        y1 = y + r
        return self.create_oval(x0, y0, x1, y1, fill='black')

    def update_circle(self,circle,x,y,r):
        x0 = x - r
        y0 = y - r
        x1 = x + r
        y1 = y + r
        self.coords(circle,x0, y0, x1, y1)


class TwoNodeElement(object):
    def __init__(self, canvas, event=None, auto_place=None):
        self.canvas = canvas
        self.grid_unit = canvas.grid_unit

        if auto_place is None and event is not None:
            self.manual_place(event)
        else:
            v = auto_place[3]
            l = auto_place[4]
            if l == '':
                l = None

            if v == '':
                v = None
            else:
                v = float(v)
            
            self.prop = [v,l]

            self.x_minus, self.y_minus = self.node_string_to_coords(
                auto_place[1])
            self.x_plus, self.y_plus = self.node_string_to_coords(
                auto_place[2])
            self.auto_place(auto_place)

    def coords_to_node_string(self, x, y):
        gu = self.grid_unit
        return "%d,%d" % (round(x/gu), round(y/gu))

    def node_string_to_coords(self, node):
        xy = node.split(',')
        x = int(xy[0])*self.grid_unit
        y = int(xy[1])*self.grid_unit
        return x, y

    def deselect(self):
        pass

    def force_select(self):
        pass

    def box_select(self, x0, y0, x1, y1):
        pass


class W(TwoNodeElement):
    def __init__(self, canvas, event=None, auto_place=None):
        self.prop = [None,None]
        self.hover = False
        self.selected = False
        self.x_minus = None
        self.y_minus = None
        self.x_plus = None
        self.y_plus = None
        super(W, self).__init__(canvas, event, auto_place)

    @property
    def pos(self):
        return [self.x_minus,self.y_minus,self.x_plus,self.y_plus]

    @pos.setter
    def pos(self,pos):
        if pos != self.pos:
            self.x_minus = pos[0]
            self.y_minus = pos[1]
            self.x_plus = pos[2]
            self.y_plus = pos[3]
            self.canvas.save()

    def manual_place(self, event):
        self.canvas.bind("<Button-1>", self.start_line)

    def auto_place(self, auto_place_info):
        self.create()

    def start_line(self, event):
        self.x_minus, self.y_minus = self.snap_to_grid(event)
        self.canvas.bind("<Motion>", self.show_line)
        self.canvas.bind("<Button-1>", self.end_line)

    def delete(self, event=None):
        self.canvas.elements.remove(self)
        self.canvas.delete(self.line)
        self.canvas.delete(self.dot_minus)
        self.canvas.delete(self.dot_plus)
        self.canvas.save()
        del self

    def end_line(self, event):
        self.canvas.delete("temp")
        self.canvas.bind("<Button-1>", lambda event: None)
        self.canvas.bind('<Motion>', lambda event: None)

        x,y = self.snap_to_grid(event)
        self.pos = [self.x_minus,self.y_minus,x,y]
        self.create()

    def create(self):
        self.line = self.canvas.create_line(*self.pos)
        self.dot_minus = self.canvas.create_circle(*self.pos[:2], self.grid_unit/20.)
        self.dot_plus = self.canvas.create_circle(*self.pos[2:], self.grid_unit/20.)
        self.canvas.elements.append(self)

    def adapt_to_gridsize(self,old_gu):
        gu = self.grid_unit
        def to_new_units(xy):
            return int(xy/old_gu)*gu
        self.pos = list(map(to_new_units,self.pos) )

        self.canvas.coords(self.line,*self.pos)
        self.canvas.update_circle(self.dot_minus,*self.pos[:2],gu/20.)
        self.canvas.update_circle(self.dot_plus,*self.pos[2:],gu/20.)


    def show_line(self, event):
        self.canvas.delete("temp")
        self.canvas.create_line(
            self.x_minus, self.y_minus, event.x, event.y, tags='temp')

    def snap_to_grid(self, event):
        gu = float(self.grid_unit)
        return int(gu * round(float(event.x)/gu)),\
            int(gu * round(float(event.y)/gu))


class Component(TwoNodeElement):
    def __init__(self, canvas, event, auto_place):
        self.image = None
        self._value = None
        self._label = None
        self.hover = False
        self.selected = False
        self.text = None
        self._x_center = None
        self._y_center = None
        self._angle = None
        super(Component, self).__init__(canvas, event, auto_place)

    @property
    def pos(self):
        return [self._x_center,self._y_center,self._angle]

    @pos.setter
    def pos(self,pos):
        if pos != self.pos:
            self._x_center = pos[0]
            self._y_center = pos[1]
            self._angle = pos[2]

            if self._angle == -90.:
                self.x_minus = pos[0]
                self.y_minus = pos[1]-self.grid_unit/2.
                self.x_plus = pos[0]
                self.y_plus = pos[1]+self.grid_unit/2.

            if self._angle == 0.:
                self.x_minus = pos[0]-self.grid_unit/2.
                self.y_minus = pos[1]
                self.x_plus = pos[0]+self.grid_unit/2.
                self.y_plus = pos[1]

            self.canvas.save()

    @property
    def prop(self):
        return [self._value,self._label]

    @prop.setter
    def prop(self,prop):
        if prop != self.prop:
            self._value = prop[0]
            self._label = prop[1]
            self.canvas.save()


    def manual_place(self, event):
        self.init_create_component(event)

    def auto_place(self, auto_place_info):

        if self.x_minus == self.x_plus:
            self.create(self.x_minus, (self.y_minus+self.y_plus)/2, -90.)
        elif self.y_minus == self.y_plus:
            self.create((self.x_minus+self.x_plus)/2, self.y_minus, 0.)
        self.add_label()
        self.canvas.elements.append(self)
        self.set_allstate_bindings()

    def request_value_label(self):
        window = RequestValueLabelWindow(self.canvas.master, self)
        self.canvas.master.wait_window(window)

    def import_tk_image(self):
        png = type(self).__name__
        if self.hover:
            png += '_hover'
        if self.selected:
            png += '_selected'
        png += '.png'

        if self.pos[2] is None:
            angle = self.init_angle
        else:
            angle = self.pos[2]

        img = Image.open(os.path.join(png_directory, png))
        self.tk_image = ImageTk.PhotoImage(img.resize(
            (self.grid_unit, self.grid_unit)).rotate(angle))

    def create(self, x, y, angle=0.):
        self.pos = [x,y,angle]
        self.import_tk_image()

        if self.image is not None:
            # Just replace tkimage
            self.canvas.itemconfig(self.image, image=self.tk_image)
            self.snap_to_grid()
        else:
            # Actually create image
            self.image = self.canvas.create_image(
                x, y, image=self.tk_image)

        if self.text is not None:
            self.add_label()

    def adapt_to_gridsize(self,old_gu):
        gu = self.grid_unit
        def to_new_units(xy):
            return int(xy/(old_gu/2.))*(gu/2.)
        self.pos = list(map(to_new_units,self.pos) )

        self.import_tk_image()
        self.canvas.itemconfig(self.image, image=self.tk_image)
        self.canvas.coords(self.image, *self.pos[:2])
        self.add_label()


    def hover_enter(self, event):
        self.hover = True

        self.import_tk_image() # this time the hover version !
        self.canvas.itemconfig(self.image, image=self.tk_image)

        self.canvas.tag_bind(self.image, "<Button-1>", self.on_click)
        self.canvas.tag_bind(self.image, "<Shift-Button-1>", 
            lambda event: self.on_click(event, shift_control=True))
        self.canvas.tag_bind(self.image, "<Control-Button-1>", 
            lambda event: self.on_click(event, shift_control=True))
        self.canvas.tag_bind(self.image, "<B1-Motion>", self.on_motion)
        self.canvas.tag_bind(
            self.image, "<ButtonRelease-1>", self.release_motion)
        self.canvas.tag_bind(
            self.image, '<Double-Button-1>', self.double_click)
        self.canvas.tag_bind(self.image, "<Shift-ButtonRelease-1>",
                             lambda event: self.release_motion(event, shift_control=True))
        self.canvas.tag_bind(self.image, "<Control-ButtonRelease-1>",
                             lambda event: self.release_motion(event, shift_control=True))

    def double_click(self,event):
        self.modify_values(self)

    def modify_values(self, event = None):
        self.request_value_label()
        self.add_label()

    def hover_leave(self, event):
        self.hover = False

        self.import_tk_image() # this time the un-hover version !
        self.canvas.itemconfig(self.image, image=self.tk_image)

    def init_create_component(self, event, angle=0.):
        self.canvas.track_changes = False
        self.init_angle = angle
        # this is written explicitely
        # since we do not want to save all positions to history
        self.import_tk_image()
        if self.image is not None:
            # Replace tkimage
            self.canvas.itemconfig(self.image, image=self.tk_image)
        else:
            # Actually create image
            self.image = self.canvas.create_image(
                event.x, event.y, image=self.tk_image)

        self.canvas.bind("<Button-1>", self.init_release)
        self.canvas.bind('<Motion>', self.on_motion)
        self.canvas.bind('<Escape>',self.abort_creation)
        self.canvas.bind(
            '<Left>', lambda event: self.init_create_component(event))
        self.canvas.bind(
            '<Right>', lambda event: self.init_create_component(event))
        self.canvas.bind(
            '<Up>', lambda event: self.init_create_component(event, angle=-90.))
        self.canvas.bind(
            '<Down>', lambda event: self.init_create_component(event, angle=-90.))

    def unset_initialization_bindings(self):
        self.canvas.bind("<Button-1>", lambda event: None)
        self.canvas.bind('<Motion>', lambda event: None)
        self.canvas.bind('<Left>', lambda event: None)
        self.canvas.bind('<Right>', lambda event: None)
        self.canvas.bind('<Up>', lambda event: None)
        self.canvas.bind('<Down>', lambda event: None)
        self.canvas.bind('<Escape>', lambda event: None)

    def abort_creation(self,event = None):
        self.unset_initialization_bindings()
        self.canvas.delete(self.image)
        del self

    def init_release(self, event):
        self.unset_initialization_bindings()
        self.snap_to_grid(event)
        self.request_value_label()
        self.add_label()
        self.canvas.elements.append(self)
        self.set_allstate_bindings()
        self.canvas.track_changes = True
        self.canvas.save()

    def set_allstate_bindings(self):
        self.canvas.tag_bind(self.image, "<Enter>", self.hover_enter)
        self.canvas.tag_bind(self.image, "<Leave>", self.hover_leave)
        self.canvas.tag_bind(self.image, "<Button-3>", self.right_click)

    def right_click(self,event):
        self.canvas.bind("<ButtonRelease-3>", self.open_right_click_menu)

    def open_right_click_menu(self,event):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit",command = self.modify_values)
        menu.add_command(label="Rotate",command = self.rotate)
        menu.add_command(label="Delete",command = self.delete)
        menu.add_separator()
        menu.add_command(label="Copy")
        menu.add_command(label="Cut")
        menu.tk_popup(event.x_root, event.y_root, 0)
        self.canvas.bind("<ButtonRelease-3>", lambda event: None)

    def rotate(self):
        if self.pos[2] == 0.:
            self.pos = [self.pos[0]-self.grid_unit/2., self.pos[1]+self.grid_unit/2., -90.]
        elif self.pos[2] == -90.:
            self.pos = [self.pos[0]+self.grid_unit/2., self.pos[1]-self.grid_unit/2., 0.]

        self.import_tk_image() # import rotated version
        self.canvas.itemconfig(self.image, image=self.tk_image)
        self.canvas.coords(self.image,self.pos[:2])
        self.add_label()



    def on_click(self, event,shift_control = False):
        if self.selected is False and shift_control is False:
            self.canvas.deselect_all()

        self.canvas.bind('<Left>', self.on_leftright)
        self.canvas.bind('<Right>', self.on_leftright)
        self.canvas.bind('<Up>', self.on_updown)
        self.canvas.bind('<Down>', self.on_updown)

    def on_motion(self, event):
        x, y = self.canvas.coords(self.image)
        dx = event.x - x
        dy = event.y - y
        self.canvas.move(self.image, dx, dy)
        if self.text is not None:
            self.canvas.move(self.text, dx, dy)

    def release_motion(self, event, shift_control=False):
        self.snap_to_grid(event)
        self.add_label()
        self.canvas.bind('<Left>', lambda event: None)
        self.canvas.bind('<Right>', lambda event: None)
        self.canvas.bind('<Up>', lambda event: None)
        self.canvas.bind('<Down>', lambda event: None)

        if shift_control:
            self.ctrl_shift_select()
        else:
            self.select()

    def on_leftright(self,event):
        self.pos = [event.x,event.y, 0.]
        self.import_tk_image() # import rotated version
        self.canvas.itemconfig(self.image, image=self.tk_image)
        self.add_label()

    def on_updown(self,event):
        self.pos = [event.x,event.y, -90.]
        self.import_tk_image() # import rotated version
        self.canvas.itemconfig(self.image, image=self.tk_image)
        self.add_label()

    def select(self):
        self.canvas.deselect_all()
        if self.selected is False:
            self.selected = True
            self.import_tk_image() # import selected circuit element
            self.canvas.itemconfig(self.image, image=self.tk_image)

    def box_select(self, x0, y0, x1, y1):
        xs = [x0, x1]
        ys = [y0, y1]
        if min(xs) <= self.pos[0] <= max(xs) and min(ys) <=  self.pos[1] <= max(ys):
            self.force_select()

    def ctrl_shift_select(self):
        if self.selected is False:
            self.selected = True
            self.import_tk_image() # import selected circuit element
            self.canvas.itemconfig(self.image, image=self.tk_image)
        elif self.selected is True:
            self.deselect()

    def force_select(self):
        self.selected = True
        self.import_tk_image() # import selected circuit element
        self.canvas.itemconfig(self.image, image=self.tk_image)

    def deselect(self):
        self.selected = False
        self.import_tk_image() # import non-selected circuit element
        self.canvas.itemconfig(self.image, image=self.tk_image)

    def delete(self, event=None):
        self.canvas.elements.remove(self)
        self.canvas.delete(self.image)
        if self.text is not None:
            self.canvas.delete(self.text)
        self.canvas.save()
        del self

    def add_label(self):

        x, y, angle = self.pos
        value,label = self.prop
        text = to_string(self.unit, label, value,
                         use_math=False, use_unicode=True)
        font = Font(family='Helvetica', size=int(self.grid_unit/8.), weight='normal')
        text_position = (0.3)*self.grid_unit
        if angle == -90. and self.text is None:
            self.text = self.canvas.create_text(
                x+text_position, y, text=text, anchor=tk.W, font=font)
        elif angle == -90. and self.text is not None:
            self.canvas.coords(self.text,x+text_position, y )
            self.canvas.itemconfig(self.text,
                text=text, anchor=tk.W, font=font)
        elif angle == 0. and self.text is None:
            self.text = self.canvas.create_text(
                x, y+text_position, text=text, anchor=tk.N, font=font)
        elif angle == 0. and self.text is not None:
            self.canvas.coords(self.text,x, y+text_position )
            self.canvas.itemconfig(self.text,
                text=text, anchor=tk.N, font=font)

    def snap_to_grid(self, event = None):
        x, y = self.canvas.coords(self.image)
        if x<self.grid_unit:
            x = self.grid_unit
        if y<self.grid_unit:
            y = self.grid_unit

        gu = float(self.grid_unit)

        if self.pos[2] is None:
            angle = self.init_angle
        else:
            angle = self.pos[2]

        if angle == -90:
            self.pos = [
                int(gu * round(float(x)/gu)),
                gu/2.+int(gu * round(float(y-gu/2.)/gu)),
                -90.]
            self.canvas.coords(self.image, self.pos[0],self.pos[1])

        elif angle == 0.:
            self.pos = [
                gu/2.+int(gu * round(float(x-gu/2.)/gu)),
                int(gu * round(float(y)/gu)),
                0.]
            self.canvas.coords(self.image, self.pos[0], self.pos[1])



class R(Component):
    """docstring for R"""

    def __init__(self, canvas, event=None, auto_place=None):
        self.unit = r'$\Omega$'
        super(R, self).__init__(canvas, event, auto_place)


class L(Component):
    """docstring for L"""

    def __init__(self, canvas, event=None, auto_place=None):
        self.unit = 'H'
        super(L, self).__init__(canvas, event, auto_place)


class C(Component):
    """docstring for C"""

    def __init__(self, canvas, event=None, auto_place=None):
        self.unit = 'F'
        super(C, self).__init__(canvas, event, auto_place)


class J(Component):
    """docstring for J"""

    def __init__(self, canvas, event=None, auto_place=None):
        self.unit = 'H'
        super(J, self).__init__(canvas, event, auto_place)


class RequestValueLabelWindow(tk.Toplevel):
    def __init__(self, master, component):
        tk.Toplevel.__init__(self, master)
        self.component = component

        # TODO add suggestions
        # TODO inform that filling two fields is optional
        fields = 'Value', 'Label'

        # Determine values of the fields
        v,l = self.component.prop
        if v is None:
            v = ''
        else:
            v = "%e"%v

        if l is None:
            l = ''
            
        field_values = [v, l]

        self.entries = []
        for i, field in enumerate(fields):
            row = tk.Frame(self)
            lab = tk.Label(row, width=7, text=field, anchor='w')
            ent = tk.Entry(row, width=7)
            ent.insert(tk.END, field_values[i])
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            lab.pack(side=tk.LEFT)
            ent.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
            self.entries.append((field, ent))
        self.entries[0][1].focus()

        self.bind('<Return>', lambda event: self.ok())
        ok_button = tk.Button(self, text='OK', command=self.ok)
        ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(self, text='Cancel', command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)

    def ok(self):
        value = self.entries[0][1].get()
        label = self.entries[1][1].get()
        if value.replace(' ','') == "":
            v = None
        else:
            try:
                v = float(value)
            except ValueError:
                messagebox.showinfo("Incorrect value", "Enter a python style float, for example: 1e-2 or 0.01")
                self.focus_force()
                return None
                

        if label.replace(' ','') == "":
            l = None
        else:
            l = label

        if l is None and v is None:
            messagebox.showinfo("No inputs", "Enter a value or a label or both")
            self.focus_force()
            return None
        else:
            self.component.prop = [v,l] 
            self.destroy()

    def cancel(self):
        self.destroy()


def open_canvas(netlist_file):
    # root = tk.Tk()
    # canvas = SnappingCanvas(root,
    #                         netlist_file=netlist_file, grid_unit=60, bg="white")
    # root.focus_force()
    # root.mainloop()
    app = MainWindow(tk.Tk(), netlist_file)
    app.mainloop()


class MainWindow(ttk.Frame):
    """ Main window class """
    def __init__(self, mainframe, netlist_file):
        """ Initialize the main Frame """
        ttk.Frame.__init__(self, master=mainframe)
        self.master.title('Circuit Editor')
        self.master.geometry('800x600')  # size of the main window
        self.master.rowconfigure(0, weight=1)  # make canvas expandable
        self.master.columnconfigure(0, weight=1)
        self.canvas = SnappingCanvas(self.master, netlist_file=netlist_file, grid_unit=60)

if __name__ == '__main__':
    open_canvas("test.txt")
