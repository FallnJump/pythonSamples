import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from collections.abc import Iterable, Callable
import numpy as np

DEFAULT_WIDTH=3
DEFAULT_COLOR="red"

def isArray(x):
	return isinstance(x, Iterable)

def process_nested_locs(xy, func, *args, **kwargs):
	"""Recursively processes nested location data using a specified function.
	Args:
		xy (list or np.ndarray): Nested list or numpy array representing location data.
	Can be in either [x, y] or [x, y, w, h] format.
		func (function): The function to be applied to each location.
		*args: Additional positional arguments for the function.
		**kwargs: Additional keyword arguments for the function.
		
	Returns:
		 list or np.ndarray: A new nested list or numpy array with the same structure as the input 'xy',
                            where each original location has been replaced by the result of `func`.
                            The type of the returned object (list or ndarray) will match the
                            input type.
	"""
	if xy is None:
		return xy
	if isArray(xy[0]):
		return [process_nested_locs(e, func, *args, **kwargs) for e in xy]
	if len(xy)>999:
		rb=[xy[0]+xy[2], xy[1]+xy[3]]
		xys=(xy[:2],rb)
		res = [e for sub in process_nested_locs(xys, func,*args, **kwargs) for e in sub]
		wh=[res[2]-res[0], res[3]-res[1]]
		return res[:2] + wh
	return func(xy, *args, **kwargs)

def for_nested_locs(func):
	"""A decorator that applies a function recursively to nested location data.

    This decorator wraps a function and enables it to process nested lists or NumPy arrays
    containing location data. The decorated function will be called on each individual,
    non-nested location array (e.g., [x, y] or [x, y, w, h]). The decorator handles
    the traversal of the nested structure, simplifying the logic of the wrapped function.

    Args:
        func (function): The function to be decorated. It should accept a single location array as its first argument, followed by any additional positional or keyword arguments.

    Returns:
        function: The decorated function.
	"""

	def wrapper(xy, *args, **kwargs):
		return process_nested_locs(xy, func, *args, **kwargs)
	return wrapper

@for_nested_locs
def rounds(xy):
	return np.round(xy).astype(int)

@for_nested_locs
def shiftscale(xywh_or_xy, shift, scale):
	p=xywh_or_xy
	if p is None or p[0] is None:
		return p
	res=np.array(p).reshape(-1, 2)
	if isArray(shift):
		shift=np.array(shift)[None]
		if len(res)>=2:
			shift=np.concatenate((shift, shift*0))
	if isArray(scale):
		scale=np.array(scale)[None]
	res=(res+shift)*scale
	return res.flatten()

def get_normalized_coord_func(obj:tk.Widget):
	"""Returns a function to normalize mouse event coordinates based on a Tkinter widget.

    This is a higher-order function that creates and returns a closure. The returned function
    takes mouse event coordinates (x, y) and normalizes them to a range of 0.0 to 1.0, using the
    dimensions of the provided Tkinter widget. This is useful for making coordinate systems
    resolution-independent, especially for drawing or interactive elements within a canvas.

    Args:
        obj (tk.Widget): A Tkinter widget instance (e.g., a Canvas or Frame) from which to
                         obtain the dimensions for normalization.

    Returns:
        function: A function that accepts two integer arguments, x and y (the mouse coordinates),
                  and returns a NumPy array containing the normalized coordinates [x_norm, y_norm].
    """
	def wh():
		if hasattr(obj, "winfo_width"):
			return np.array((obj.winfo_width(), obj.winfo_height()))
		return obj.getSize()
	def resf_fw(xy):
		return xy/wh()
	return resf_fw

def get_closest_point(xy1, xy2):
	"""Calculates a point on the line segment from xy1 to xy2 that is closest to xy1, 
    but with a distance equal to the smaller of the two dimensions.

    This function determines the shorter dimension (width or height) between two points,
    then returns a new point that is that same distance away from the starting point (xy1)
    along the correct direction (either x, y, or both). This is useful for scenarios
    like finding the closest point of intersection on an axis-aligned bounding box.

    Args:
        xy1 (np.ndarray): The starting point, typically a 2D NumPy array [x1, y1].
        xy2 (np.ndarray): The ending point, typically a 2D NumPy array [x2, y2].

    Returns:
        np.ndarray: A 2D NumPy array representing the new point.
	"""
	swh=xy2-xy1
	wh=np.abs(swh)
	# distance
	whmin=np.min(wh)
	# direction
	sgns=np.sign(swh)
	return xy1+sgns*whmin

class Motion:
	"""Manages mouse events to track state and position, and execute callbacks.

    This class captures mouse events (button presses, releases, and drags) to store
    the button state, start position, and end position. It normalizes coordinates based on
    a provided widget's dimensions, making the data independent of window resizing.
    A callback function is triggered with the start position, end position, and
    button state when a mouse button is released.

    Attributes:
        callbk (Callable): The function to call on mouse button release.
        posNormalizer (Callable): A function that normalizes coordinates.
        stpos (Optional[np.ndarray]): The normalized coordinates of the button press.
        lack_aspect_ratio (bool): If True, constrains X and Y movement to be equal to maintain aspect ratio.
	"""
	MOTION_ST=0
	MOTION_MV=1
	MOTION_ED=2	
	def __init__(self, callbk, posNormalizer=None):
		self.stpos = None
		self.stpos_raw=None
		self.callbk=callbk
		self.posNormalizer=posNormalizer
		self.lack_aspect_ratio=False
	
	def runCallbk(self, edpos, mode):
		if hasattr(edpos, "x"):
			edpos=np.array((edpos.x, edpos.y))
		if self.callbk is not None and self.stpos is not None:
			stpos=self.stpos
			if self.lack_aspect_ratio:
				edpos=get_closest_point(self.stpos_raw, edpos)
			edpos=self.normalize(edpos)
			self.callbk(stpos, edpos, mode)
	
	def normalize(self, xy):
		if self.posNormalizer is None:
			return xy
		return self.posNormalizer(xy)
	
	def bind(self, obj:tk.Widget):
		obj.bind("<Button-1>", self.start)
		obj.bind("<ButtonRelease-1>", self.end)
		obj.bind("<B1-Motion>", self.mov)

	def start(self, e):
		self.stpos_raw=np.array((e.x,e.y))
		self.stpos=self.normalize(self.stpos_raw)
		self.runCallbk(self.stpos_raw, self.MOTION_ST)

	def mov(self, e):
		self.runCallbk(e, self.MOTION_MV)
	
	def end(self, e):
		self.runCallbk(e, self.MOTION_ED)
		self.stpos=None

class RectHelper:
	"""A utility class for flexible rectangle manipulation."""
	def __init__(self, xy=None, wh=None):
		self.xy=xy
		self.wh=wh

	def setByPoints(self, xy1, xy2):
		lt=np.minimum(xy1, xy2)
		rb=np.maximum(xy1, xy2)
		self.xy=(lt+rb)/2
		self.wh=rb-lt
	
	def setByCtSide(self, ct, xy):
		dxy=np.abs(xy-ct)
		self.wh=dxy*2
	
	def setByXywh(self, xy, wh):
		self.xy=xy
		self.wh=wh
	
	def setByRefer(self, referRect):
		self.xy=referRect.xy
		self.wh=referRect.wh
	
	def setByAuto(self, xy1, xy2):
		if self.xy is None and self.wh is None:
			self.setByPoints(xy1, xy2)
		elif self.xy is None:
			self.xy=xy2
		elif self.wh is None:
			self.setByCtSide(self.xy, xy2)
	
	def isValid(self):
		return self.xy is not None and self.wh is not None

class RectModifier(RectHelper):
	"""A class to modify a rectangle's position or size based on mouse events.

    This class extends RectangleHelper to provide dynamic manipulation capabilities.
    It works in a specific mode (e.g., move, resize) to update a stored rectangle's
    coordinates or dimensions according to user input from a mouse event manager.
    It is designed to be used with a MouseEventManager to provide interactive
    resizing and repositioning of a rectangle, maintaining its integrity throughout
    the process.
    """
	MODE_XY=1
	MODE_WH=2
	MODE_ALL=3
	def __init__(self):
		super().__init__()
		self.lastDecide=RectHelper()
		self.mode=self.MODE_XY
	
	@staticmethod
	def getModeList():
		dct=__class__.__dict__
		lst=[(k, v) for k, v in dct.items() if k.startswith("MODE_")]
		return lst

	def reload(self, st, ed, mode):
		self.setByRefer(self.lastDecide)
		if self.mode & self.MODE_XY:
			self.xy=None
		if self.mode & self.MODE_WH:
			self.wh=None
		self.setByAuto(st, ed)
		if mode==Motion.MOTION_ED:
			self.lastDecide.setByRefer(self)
	
	def getLtrb(self):
		if self.xy is None or self.wh is None:
			return None
		lt=self.xy-self.wh/2
		rb=lt+self.wh
		return np.concatenate((lt, rb))

def drawCross(obj:tk.Canvas, xy, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	sz=obj.winfo_width()//30
	xv, yv=np.eye(2)*sz
	ln1=np.stack((xy-xv, xy+xv))
	ln2=np.stack((xy-yv, xy+yv))
	lines=rounds((ln1, ln2))
	for ln in lines:
		obj.create_line(*ln[0],*ln[1], fill=clr, width=width, tags="drawing")

def drawLine(obj:tk.Canvas, xy1, xy2, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	obj.create_line(*rounds(xy1), *rounds(xy2), fill=clr, width=width, tags="drawing")

def drawBox(obj:tk.Canvas, ltrb, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	ltrb=rounds(ltrb)
	obj.create_rectangle(*ltrb, width=width, outline=clr, tags="drawing")

def ratio2Obj(obj:tk.Widget, *args):
	w=obj.winfo_width()
	h=obj.winfo_height()
	wh=np.array((w,h))
	ress=[]
	for arg in args:
		res=[]
		xys=arg.reshape(-1, 2)
		res=(xys*wh[None]).flatten()
		ress.append(res)
	return ress

class InteractiveShapeModifier:
	"""Modifies the position or dimensions of a shape based on mouse events and a specified mode."""
	MODE_POS=0
	MODE_BOX=1
	MODE_LINE=2
	def __init__(self):
		self.mode=self.MODE_POS
		self.rctctl=RectModifier()
		self.xys=None
	
	def setRect(self, xywh):
		self.mode=self.MODE_BOX
		if xywh is not None:
			self.rctctl.xy=xywh[:2]
			self.rctctl.wh=xywh[2:]
		else:
			self.rctctl.xy=self.rctctl.wh=None
		self.rctctl.lastDecide.setByRefer(self.rctctl)
	
	def setPos(self, xy):
		self.mode=self.MODE_POS
		self.xys=[xy]
	
	def setLine(self, xys):
		self.mode=self.MODE_LINE
		self.xys=xys
	
	def isPos(self):
		return self.mode==self.MODE_POS
	
	def isBox(self):
		return self.mode==self.MODE_BOX
	
	def isLine(self):
		return self.mode==self.MODE_LINE
	
	def getPos(self):
		if self.isPos():
			return self.xys[0]
		
		if self.isLine():
			return self.xys
		
		if self.isBox():
			return np.concatenate([self.rctctl.xy, self.rctctl.wh])
		
		return None
	
	def setMouse(self, st, ed, mode):
		if self.isPos():
			self.xys=[ed]
		if self.isLine():
			self.xys=(st, ed)
		if self.isBox():
			self.rctctl.reload(st, ed, mode)
	
	def draw(self, obj:tk.Canvas):
		obj.delete("drawing")
		if self.xys is not None:
			xys=ratio2Obj(obj, *self.xys)
			if self.isPos():
				drawCross(obj, xys[0])
			if self.isLine():
				drawLine(obj, *xys)
		if self.isBox() and self.rctctl.isValid():
			ltrb=self.rctctl.getLtrb()
			ltrb=ratio2Obj(obj, ltrb)[0]
			drawBox(obj, ltrb)

class ImageFitter:
	"""Manages image display and coordinate conversion within a canvas.

    This class automatically fits an image to a canvas, handling scaling and
    positioning. It provides methods for converting coordinates between three
    different systems: the canvas, the displayed (scaled) image, and the original image.
    This functionality is essential for accurately mapping user interactions on the canvas
    to specific pixels on the source image, especially when the image's dimensions
    differ from the canvas.
	"""
	COORD_RAW=0
	COORD_CLIENT=1
	COORD_CVS=2
	COORD_ORG=3
	COORD_IMRATIO=4
	def __init__(self, im, obj:tk.Canvas):
		self.orgim=im
		self.img=None
		self.obj=obj
		self.toTk()
	
	def getClientSize(self):
		return np.array((self.obj.winfo_width(), self.obj.winfo_height()))
	
	def getDrawLtwh(self):
		return self.ltwh
	
	def getOrgSize(self):
		return np.array((self.orgim.width, self.orgim.height))
	
	def getSizes(self):
		return (self.getClientSize(), self.getDrawLtwh(), self.getOrgSize())
	
	def toTk(self):
		orgwh=self.getOrgSize()
		wh=self.getClientSize()
		asp_wh=wh/orgwh
		asp=np.min(asp_wh)
		nwh=np.floor(orgwh*asp)
		nwh=np.maximum(nwh, 1)
		im=self.orgim.resize(nwh.astype(int))
		self.img=ImageTk.PhotoImage(im)
		ltpos=(wh-nwh)//2
		self.ltwh=np.concatenate((ltpos, nwh)).astype(int)
	
	def putImage(self, tags):
		self.obj.create_image(self.ltwh[0], self.ltwh[1], anchor=tk.NW, image=self.img, tags=tags)

	@staticmethod
	@for_nested_locs
	def _getClientPosAt(xy, refsz):
		return np.round(shiftscale(xy, 0, refsz))
	
	def getClientPosAt(self, xy):
		return self._getClientPosAt(xy, self.getClientSize())

	@staticmethod
	@for_nested_locs
	def _getImRatioAt(xy, refsz, imltwh):
		xy=__class__._getClientPosAt(xy, refsz)
		dxy=shiftscale(xy, -imltwh[:2], 1/imltwh[2:])
		return dxy
	
	def getImRatioAt(self, xy):
		return self._getImRatioAt(xy, self.getClientSize(), self.getDrawLtwh())

	@staticmethod
	@for_nested_locs
	def _getImCvsPosAt(xy, refsz, imltwh):
		xy=__class__._getClientPosAt(xy, refsz)
		dxy=shiftscale(xy, -imltwh[:2], 1)
		return np.round(dxy)
	
	def getImCvsPosAt(self, xy):
		return self._getImCvsPosAt(xy, self.getClientSize(), self.getDrawLtwh())

	@staticmethod
	@for_nested_locs
	def _getImOrgPosAt(xy, refsz, imltwh, orgwh):
		xy=__class__._getClientPosAt(xy, refsz)
		dxy=shiftscale(xy, -imltwh[:2], orgwh/imltwh[2:])
		return np.round(dxy)
	
	def getImOrgPosAt(self, xy):
		return self._getImOrgPosAt(xy, *self.getSizes())

	@staticmethod
	@for_nested_locs
	def _getFromClientPos(xy, refsz):
		return shiftscale(xy, 0, 1/refsz)

	def getFromClientPos(self, xy):
		return self._getFromClientPos(xy, self.getClientSize())

	@staticmethod
	@for_nested_locs
	def _getFromImCvsPos(xy, refsz, imltwh, orgwh):
		return shiftscale(xy, imltwh[:2], 1/refsz)
	
	def getFromCvsPos(self, xy):
		return self._getFromImCvsPos(xy, *self.getSizes())

	@staticmethod
	@for_nested_locs
	def _getFromImOrgPos(xy, refsz, imltwh, orgwh):
		return shiftscale(xy, imltwh[:2]/imltwh[2:]*orgwh, imltwh[2:]/orgwh/refsz)
	
	def getFromImOrgPos(self, xy):
		return self._getFromImOrgPos(xy, *self.getSizes())
	
	@staticmethod
	@for_nested_locs
	def _getFromImRatio(xy, refsz, imltwh, orgwh):
		print(imltwh, refsz)
		return shiftscale(xy, imltwh[:2]/imltwh[2:], imltwh[2:]/refsz)
	
	def getFromImRatio(self, xy):
		return self._getFromImRatio(xy, *self.getSizes())
	
	def getPosAt(self, xy, geokind):
		f={
			__class__.COORD_CLIENT: self.getClientPosAt,
			__class__.COORD_CVS: self.getImCvsPosAt,
			__class__.COORD_IMRATIO: self.getImRatioAt,
			__class__.COORD_ORG: self.getImOrgPosAt,
			__class__.COORD_RAW: lambda p:p
		}
		assert(geokind in f)
		return f[geokind](xy)
	
	def getFromPos(self, xy, geokind):
		f={
			__class__.COORD_CLIENT: self.getFromClientPos,
			__class__.COORD_CVS: self.getFromCvsPos,
			__class__.COORD_IMRATIO: self.getFromImRatio,
			__class__.COORD_ORG: self.getFromImOrgPos,
			__class__.COORD_RAW: lambda p:np.array(p)
		}
		assert(geokind in f)
		print(xy, f[geokind](xy))
		return f[geokind](xy)

class InteractiveShapeCanvas(tk.Canvas):
	"""A Tkinter canvas subclass for interactive shape creation and manipulation

    This class extends the standard `tk.Canvas` to capture mouse events and parse
    the start and end positions of a mouse press into shape coordinates. Based on a
    pre-selected mode (e.g., 'rectangle', 'line', 'point'), it interprets these
    coordinates and passes them to a user-defined callback function. It's designed
    to provide a streamlined way to create and edit shapes on a canvas using a
    mouse, abstracting away the raw event handling logic.
    """
	def __init__(self, root):
		super().__init__(root, bg="black")
		self.img=None
		self.imfit=None
		self.mt=Motion(self.onMouse, get_normalized_coord_func(self))
		self.posctl=InteractiveShapeModifier()
		self.mt.bind(self)
		self.onSel:Callable
		self.onSel=None
		self.root=root
		self.coordMode=ImageFitter.COORD_IMRATIO

	def onMouse(self, st, ed, mode):
		self.delete("drawing")
		self.posctl.setMouse(st,ed,mode)
		self.posctl.draw(self)
		if self.onSel:
			pos=self.imfit.getPosAt(self.posctl.getPos(), self.coordMode)
			self.onSel(pos, self.posctl)
	
	def coordCvt(self, xy):
		if self.imfit is None:
			return xy
		return self.imfit.getFromPos(xy, self.coordMode)
	
	def setRect(self, xywh):
		self.posctl.setRect(self.coordCvt(xywh))
	
	def setRectMode(self, rectMode):
		self.posctl.rctctl.mode=rectMode
	
	def setLine(self, xy1, xy2):
		self.posctl.setLine(self.coordCvt((xy1, xy2)))
	
	def setPos(self, xy):
		self.posctl.setPos(self.coordCvt(xy))
	
	def getPos(self):
		pos=self.posctl.getPos()
		if self.imfit:
			pos=self.imfit.getPosAt(pos, self.coordMode)
		return pos
	
	def setWhFix(self, onoff):
		self.mt.bwheq=onoff
	
	def open(self, imc):
		self.root.update_idletasks()
		self.delete("srcim")
		if self.img is not None:
			del self.img
		if isinstance(imc, str):
			im=Image.open(imc)
		elif isinstance(imc, tuple):
			im=Image.new("RGB", size=imc[:2], color=imc[2])
		else:
			im=imc
		self.imfit = ImageFitter(im, self)
		self.imfit.putImage("srcim")


if __name__=="__main__":
	# usecase
	root = tk.Tk()
	canvas = InteractiveShapeCanvas(root)
	canvas.pack(fill=tk.BOTH, expand=True)
	root.update_idletasks()
	canvas.open((256,256,"#cfc"))
	canvas.setRect(None)
	#canvas.setLine(None,None)
	#canvas.setWhFix(True)
	#canvas.setRectMode(RectCtrl.MODE_ALL)
	#canvas.open("path/to/image")
	def wheq(poses, mode):
		if mode != InteractiveShapeModifier.MODE_BOX:
			return poses
		wh=ratio2Obj(canvas, *poses)[1]
		wh=[min(*wh)]*2
		wh=get_normalized_coord_func(canvas)(wh)
		return poses[0], wh
	root.mainloop()
