import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from collections.abc import Iterable
from math import floor

def isArray(x):
	return isinstance(x, Iterable)

DEFAULT_WIDTH=3
DEFAULT_COLOR="red"

def getConvFunc(obj:tk.Widget):
	def wh():
		if hasattr(obj, "winfo_width"):
			return obj.winfo_width(), obj.winfo_height()
		return obj.getSize()
	def resf_fw(xy):
		w,h=wh()
		x,y=xy
		x=x/w
		y=y/h
		return x,y
	return resf_fw

def FixEd(xy1, xy2):
	swh=[(e2-e1) for e1,e2 in zip(xy1,xy2)]
	wh=[abs(e) for e in swh]
	whmin=min(*wh)
	swh=[(1 if e1>0 else -1)*whmin for e1 in swh]
	xy2=[e1+s for e1,s in zip(xy1, swh)]
	return xy2

class Motion:
	MOTION_ST=0
	MOTION_MV=1
	MOTION_ED=2
	def __init__(self, callbk, getConvfunc=None):
		self.stpos = None
		self.stpos_raw=None
		self.callbk=callbk
		self.getConvfunc=getConvfunc
		self.bwheq=False
	
	def runCallbk(self, edpos, mode):
		if hasattr(edpos, "x"):
			edpos=(edpos.x, edpos.y)
		if self.callbk is not None and self.stpos is not None:
			stpos=self.stpos
			if self.bwheq:
				edpos=FixEd(self.stpos_raw, edpos)
			edpos=self.convPos(edpos)
			self.callbk(stpos, edpos, mode)
	
	def convPos(self, xy):
		if self.getConvfunc is None:
			return xy
		return self.getConvfunc(xy)
	
	def bind(self, obj:tk.Widget):
		obj.bind("<Button-1>", self.start)
		obj.bind("<ButtonRelease-1>", self.end)
		obj.bind("<B1-Motion>", self.mov)

	def start(self, e):
		self.stpos_raw=(e.x,e.y)
		self.stpos=self.convPos((e.x,e.y))
		self.runCallbk((e.x,e.y), self.MOTION_ST)

	def mov(self, e):
		self.runCallbk(e, self.MOTION_MV)
	
	def end(self, e):
		self.runCallbk(e, self.MOTION_ED)
		self.stpos=None

class Rect:
	def __init__(self, xy=None, wh=None):
		self.xy=xy
		self.wh=wh

	def setByPoints(self, xy1, xy2):
		L = min(xy1[0], xy2[0])
		T = min(xy1[1], xy2[1])
		R = max(xy1[0], xy2[0])
		B = max(xy1[1], xy2[1])
		self.xy=((L+R)/2, (T+B)/2)
		self.wh=(R-L, B-T)
	
	def setByCtSide(self, ct, xy):
		dx=abs(xy[0]-ct[0])
		dy=abs(xy[1]-ct[1])
		self.wh=(dx*2, dy*2)
	
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
			self.wh=[(p2-p1)*2 for p1,p2 in zip(self.xy, xy2)]

	def getLtrb(self):
		if not self.isValid():
			return None
		x,y=self.xy
		w,h=self.wh
		left=x-w/2
		top=y-h/2
		right=x+w/2
		bottom=y+h/2
		return (left, top, right, bottom)
	
	def isValid(self):
		return self.xy is not None and self.wh is not None

class RectCtrl(Rect):
	MODE_XY=1
	MODE_WH=2
	MODE_ALL=3
	def __init__(self):
		super().__init__()
		self.lastDecide=Rect()
		self.mode=self.MODE_XY
	
	def reload(self, st, ed, mode):
		self.setByRefer(self.lastDecide)
		if self.mode & self.MODE_XY:
			self.xy=None
		if self.mode & self.MODE_WH:
			self.wh=None
		self.setByAuto(st, ed)
		if mode==Motion.MOTION_ED:
			self.lastDecide.setByRefer(self)

def rounds(*args):
	return [rounds(*a) if isArray(a) else int(round(a)) for a in args]

def drawCross(obj:tk.Canvas, xy, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	sz=obj.winfo_width()//30
	lines=rounds(((xy[0]-sz, xy[1]), (xy[0]+sz, xy[1])), ((xy[0],xy[1]-sz),(xy[0],xy[1]+sz)))
	for ln in lines:
		obj.create_line(*ln, fill=clr, width=width, tags="drawing")

def drawLine(obj:tk.Canvas, xy1, xy2, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	obj.create_line(rounds(xy1), rounds(xy2), fill=clr, width=width, tags="drawing")

def drawBox(obj:tk.Canvas, ltrb, width=DEFAULT_WIDTH, clr=DEFAULT_COLOR):
	ltrb=rounds(ltrb)
	obj.create_rectangle(ltrb[:2], ltrb[2:],width=width, outline=clr, tags="drawing")

def ratio2Obj(obj:tk.Widget, *args):
	w=obj.winfo_width()
	h=obj.winfo_height()
	wh=w,h
	ress=[]
	for arg in args:
		res=[]
		for n, p in enumerate(arg):
			res.append(p*wh[n%2])
		ress.append(res)
	return ress


class RectPos:
	MODE_POS=0
	MODE_BOX=1
	MODE_LINE=2
	def __init__(self):
		self.mode=self.MODE_POS
		self.rctctl=RectCtrl()
		self.xys=None
	
	def setRect(self, xywh):
		self.mode=self.MODE_BOX
		if xywh is not None:
			self.rctctl.xy=xywh[:2]
			self.rctctl.wh=xywh[2:]
		else:
			self.rctctl.xy=self.rctctl.wh=None
	
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
			return [*self.rctctl.xy, *self.rctctl.wh]
		
		return None
	
	def setMouse(self, st, ed, mode):
		if self.isPos():
			self.xys=ed
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

class CanvasUI(tk.Canvas):
	def __init__(self, root):
		super().__init__(root, bg="black")
		self.img=None
		self.mt=Motion(self.onMouse, getConvFunc(self))
		self.posctl=RectPos()
		self.mt.bind(self)
		self.ltwh=None
		self.lastsel=None
		self.cursel=None
		
	def onMouse(self, st, ed, mode):
		self.delete("drawing")
		self.posctl.setMouse(st,ed,mode)
		self.posctl.draw(self)
	
	def setRect(self, xywh):
		self.posctl.setRect(xywh)
	
	def setRectMode(self, rectMode):
		self.posctl.rctctl.mode=rectMode
	
	def setLine(self, xy1, xy2):
		self.setLine(xy1, xy2)
	
	def setPos(self, xy):
		self.posctl.setPos(xy)
	
	def getPos(self):
		return self.posctl.getPos()
	
	def setFilter(self, f):
		self.posctl.filterfunc=f
	
	def setWhFix(self, onoff):
		self.mt.bwheq=onoff
		
	def open(self, imc):
		self.delete("srcim")
		if self.img is not None:
			del self.img
		if isinstance(imc, str):
			im=Image.open(imc)
		elif isinstance(imc, tuple):
			im=Image.new("RGB", size=imc[:2], color=imc[2])
		else:
			im=imc
		orgwh=(im.width, im.height)
		w,h=self.winfo_width(), self.winfo_height()
		asp_w=w/orgwh[0]
		asp_h=h/orgwh[1]
		asp=min(asp_w, asp_h)
		nw=floor(orgwh[0]*asp)
		nh=floor(orgwh[1]*asp)
		nw=max(1, nw)
		nh=max(1, nh)
		im=im.resize((nw, nh))
		self.img=ImageTk.PhotoImage(im)
		lpos=(w-nw)//2
		tpos=(h-nh)//2
		self.ltwh=(lpos, tpos, nw, nh)
		self.create_image(lpos, tpos, anchor=tk.NW, image=self.img, tags="srcim")

if __name__=="__main__":
	# usecase
	root = tk.Tk()
	canvas = CanvasUI(root)
	canvas.pack(fill=tk.BOTH, expand=True)
	root.update_idletasks()
	canvas.open((256,256,"#cfc"))
	canvas.setRect(None)
	#canvas.setWhFix(True)
	#canvas.setRectMode(RectCtrl.MODE_ALL)
	#canvas.open("path/to/image")
	def wheq(poses, mode):
		if mode != RectPos.MODE_BOX:
			return poses
		wh=ratio2Obj(canvas, *poses)[1]
		wh=[min(*wh)]*2
		wh=getConvFunc(canvas)(wh)
		return poses[0], wh
	canvas.setFilter(wheq)
	
	root.mainloop()

