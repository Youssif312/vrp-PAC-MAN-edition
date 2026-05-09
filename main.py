import pygame, math, random, sys, os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

_SR = 22050
_MIXER_READY = False
try:
    pygame.mixer.pre_init(_SR, -16, 1, 1024)
    pygame.mixer.init(_SR, -16, 1, 1024)
    _MIXER_READY = True
except Exception as _e:
    print(f"[sound] mixer init failed: {_e}")

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)
try:
    import vrp_logic as _logic
    _LOGIC_OK = True
except ImportError as _ie:
    print(f"[vrp] vrp_logic.py not found — {_ie}")
    _LOGIC_OK = False

PX_TO_KM = 0.01


def build_distance_matrix(depot, customers):
    import numpy as _np
    nodes = [(depot.x, depot.y)] + [(c.x, c.y) for c in customers]
    n = len(nodes)
    mat = _np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dx = nodes[i][0] - nodes[j][0]; dy = nodes[i][1] - nodes[j][1]
            mat[i][j] = (dx*dx + dy*dy) ** 0.5
    return mat

def decode_logic_chromosome(chrom, customers):
    routes=[]; vid=0; cur=[]
    for g in chrom:
        if g==0:
            r=Route(vid); r.nodes=[customers[x-1] for x in cur]; routes.append(r); vid+=1; cur=[]
        else:
            cur.append(g)
    if cur:
        r=Route(vid); r.nodes=[customers[x-1] for x in cur]; routes.append(r)
    return routes

def run_logic_ga(depot, customers, demands, n_vehicles, v_cap, pop_size, n_gen):
    if not _LOGIC_OK or not customers: return [],[]
    matrix=build_distance_matrix(depot,customers)
    total_d=sum(demands[1:]); min_v=math.ceil(total_d/v_cap)
    actual_v=max(n_vehicles, min_v)
    population=_logic.initialization_population(pop_size,demands,actual_v,v_cap,len(customers))
    history=[]; best_route=None; best_fit=-1.0
    elite_k=max(1,int(0.2*pop_size))
    for _ in range(n_gen):
        fits=[_logic.fitness(ind,matrix,demands,v_cap) for ind in population]
        gb=max(fits); ga_=sum(fits)/len(fits); history.append((gb,ga_))
        bi=fits.index(gb)
        if gb>best_fit: best_fit=gb; best_route=population[bi]
        sp=sorted(zip(fits,population),reverse=True)
        new=[ind for _,ind in sp[:elite_k]]
        ri=random.randint(elite_k,pop_size-1); new.append(sp[ri][1])
        while len(new)<pop_size:
            p1=_logic.selection(population,fits); p2=_logic.selection(population,fits)
            new.append(_logic.order_crossover(p1,p2,demands,v_cap))
        new=_logic.mutate_population(new); population=new
    return decode_logic_chromosome(best_route,customers), history


_SOUND_DIR = os.path.join(_DIR, "sounds")
_SOUND_NAMES = ["waka","click","depot","solve","victory","clear","randomize"]

class SoundManager:
    def __init__(self):
        self._sounds={}; self._enabled=_MIXER_READY
        if not _MIXER_READY: return
        for name in _SOUND_NAMES:
            snd = self._try_load_file(name)
            if snd is None:
                snd = self._synth_fallback(name)
            if snd is not None:
                self._sounds[name] = snd
        print(f"[sound] {len(self._sounds)}/{len(_SOUND_NAMES)} sounds loaded")

    def _try_load_file(self, name):
        for ext in (".wav", ".mp3", ".ogg"):
            path = os.path.join(_SOUND_DIR, name + ext)
            if os.path.isfile(path):
                try:
                    s = pygame.mixer.Sound(path)
                    print(f"[sound] loaded {name}{ext}")
                    return s
                except Exception as e:
                    print(f"[sound] failed to load {path}: {e}")
        return None

    def _synth_fallback(self, name):
        if not _HAS_NUMPY: return None
        try:
            def tone(freq,dur,vol=0.3,decay=8):
                n=int(_SR*dur); t=np.linspace(0,dur,n,endpoint=False)
                w=np.sign(np.sin(2*np.pi*freq*t))*np.exp(-decay*t)*vol
                return (np.clip(w,-1,1)*32767).astype(np.int16)
            tones={
                "waka":    np.concatenate([tone(440,.045),tone(330,.045)]),
                "click":   tone(880,.03,decay=25),
                "depot":   np.concatenate([tone(523,.06,decay=10),tone(659,.06,decay=10)]),
                "solve":   np.concatenate([tone(200+i*60,.025,decay=5) for i in range(8)]),
                "victory": np.concatenate([tone(f,.12,decay=4) for f in [523,659,784,1047]]),
                "clear":   np.concatenate([tone(400-i*45,.04,decay=6) for i in range(7)]),
                "randomize":np.concatenate([tone(random.randint(300,900),.018,decay=15) for _ in range(6)]),
            }
            arr=tones.get(name)
            return pygame.mixer.Sound(buffer=arr.tobytes()) if arr is not None else None
        except Exception as e:
            print(f"[sound] synth failed for {name}: {e}"); return None

    def play(self,name):
        if not self._enabled: return
        s=self._sounds.get(name)
        if s: s.play()

    def toggle(self):
        self._enabled=not self._enabled; return self._enabled


BG          = (  0,   0,   0)
PANEL_BG    = (  5,   5,  30)
BORDER      = ( 33,  33, 200)
TEXT_PRI    = (255, 255,   0)
TEXT_SEC    = (200, 160, 255)
DEPOT_COL   = (255, 255,   0)
ACCENT      = ( 33, 200, 200)
BTN_BG      = (  5,   5,  55)
BTN_HOV     = ( 33,  33, 120)
BTN_SOLVE   = (  0, 160,   0)
BTN_SOLVE_H = (  0, 210,   0)
BTN_CLR     = (180,   0,   0)
BTN_CLR_H   = (230,  40,  40)
BTN_RAND    = (150,   0, 150)
BTN_RAND_H  = (200,  40, 200)
ROUTE_ALPHA = 160
GRAPH_BG    = (  0,   0,  15)
GRAPH_BEST  = (255, 230,   0)
GRAPH_AVG   = (200, 140, 255)
GRAPH_GRID  = ( 18,  18,  70)

VEHICLE_COLORS=[
    (255,180,255),(33,220,220),(255,180,80),(255,80,80),
    (255,255,0),(0,255,120),(180,80,255),(255,255,255),
]

W=1200; H=850
PANEL_W=260; CANVAS_X=PANEL_W; CANVAS_W=W-PANEL_W
GRAPH_H=160; GRAPH_Y=H-GRAPH_H
NODE_R=8; DEPOT_R=12


@dataclass
class Node:
    x:float; y:float; idx:int; demand:int=1

@dataclass
class Route:
    vehicle_id:int
    nodes:List[Node]=field(default_factory=list)

def dist(a,b): return math.hypot(a.x-b.x,a.y-b.y)
def route_dist_nodes(depot,nodes):
    if not nodes: return 0.0
    d=dist(depot,nodes[0])
    for i in range(len(nodes)-1): d+=dist(nodes[i],nodes[i+1])
    d+=dist(nodes[-1],depot); return d
def total_route_distance(depot,route): return route_dist_nodes(depot,route.nodes)
def route_km(depot,route): return total_route_distance(depot,route)*PX_TO_KM
def build_waypoints(depot,route):
    pts=[(depot.x,depot.y)]
    for n in route.nodes: pts.append((n.x,n.y))
    pts.append((depot.x,depot.y)); return pts


def draw_truck(surf,x,y,angle_rad,color,scale=1.0):
    r=int(12*scale); t=pygame.time.get_ticks()/1000.0
    mouth=abs(math.sin(t*8))*35; mr=math.radians(mouth)
    cx,cy=int(x),int(y); pts=[(cx,cy)]
    sa=angle_rad+mr; ea=angle_rad+2*math.pi-mr
    for i in range(31):
        a=sa+(ea-sa)*i/30; pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    sh=pygame.Surface((r*4,r*4),pygame.SRCALPHA)
    pygame.draw.polygon(sh,(0,0,0,50),[(p[0]-cx+r*2+3,p[1]-cy+r*2+3) for p in pts])
    surf.blit(sh,(cx-r*2,cy-r*2))
    pygame.draw.polygon(surf,color,pts)
    ex=cx+int(r*0.35*math.cos(angle_rad-math.pi/2))
    ey=cy+int(r*0.35*math.sin(angle_rad-math.pi/2))
    pygame.draw.circle(surf,(0,0,0),(ex,ey),max(2,int(2.5*scale)))


@dataclass
class TruckAnim:
    route:Route; waypoints:List[Tuple[float,float]]; color:Tuple[int,int,int]
    seg_idx:int=0; seg_t:float=0.0; done:bool=False
    trail:List[Tuple[float,float]]=field(default_factory=list)
    visited:set=field(default_factory=set)
    flash_timers:dict=field(default_factory=dict)

    def current_pos(self):
        if self.seg_idx>=len(self.waypoints)-1: return self.waypoints[-1]
        ax,ay=self.waypoints[self.seg_idx]; bx,by=self.waypoints[self.seg_idx+1]
        return (ax+(bx-ax)*self.seg_t,ay+(by-ay)*self.seg_t)

    def current_angle(self):
        if self.seg_idx>=len(self.waypoints)-1: return 0.0
        ax,ay=self.waypoints[self.seg_idx]; bx,by=self.waypoints[self.seg_idx+1]
        return math.atan2(by-ay,bx-ax)

    def advance(self,dt,speed):
        if self.done: return
        wps=self.waypoints
        while dt>0:
            if self.seg_idx>=len(wps)-1: self.done=True; return
            ax,ay=wps[self.seg_idx]; bx,by=wps[self.seg_idx+1]
            sl=math.hypot(bx-ax,by-ay)
            if sl<0.5: self.seg_idx+=1; self.seg_t=0.0; continue
            rem=(1.0-self.seg_t)*sl; df=speed*dt
            if df<rem: self.seg_t+=df/sl; dt=0
            else:
                dt-=rem/speed; self.seg_idx+=1; self.seg_t=0.0
                wp=self.seg_idx
                if 1<=wp<=len(self.route.nodes):
                    n=self.route.nodes[wp-1]; self.visited.add(n.idx); self.flash_timers[n.idx]=0.5
        self.trail.append(self.current_pos())
        if len(self.trail)>30: self.trail.pop(0)


class Button:
    def __init__(self,rect,label,color,hover,font):
        self.rect=pygame.Rect(rect); self.label=label; self.color=color; self.hover=hover; self.font=font
    def draw(self,surf):
        c=self.hover if self.rect.collidepoint(pygame.mouse.get_pos()) else self.color
        pygame.draw.rect(surf,c,self.rect,border_radius=6)
        pygame.draw.rect(surf,BORDER,self.rect,1,border_radius=6)
        t=self.font.render(self.label,True,TEXT_PRI); surf.blit(t,t.get_rect(center=self.rect.center))
    def clicked(self,ev):
        return ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1 and self.rect.collidepoint(ev.pos)

class Spinbox:
    def __init__(self,rect,value,mn,mx,font):
        self.rect=pygame.Rect(rect); self.value=value; self.mn=mn; self.mx=mx; self.font=font
        bw=24
        self.bd=pygame.Rect(rect[0],rect[1],bw,rect[3])
        self.bi=pygame.Rect(rect[0]+rect[2]-bw,rect[1],bw,rect[3])
    def draw(self,surf):
        pygame.draw.rect(surf,PANEL_BG,self.rect,border_radius=5)
        pygame.draw.rect(surf,BORDER,self.rect,1,border_radius=5)
        for b,sym in((self.bd,'−'),(self.bi,'+')):
            c=BTN_HOV if b.collidepoint(pygame.mouse.get_pos()) else BTN_BG
            pygame.draw.rect(surf,c,b,border_radius=4)
            t=self.font.render(sym,True,TEXT_PRI); surf.blit(t,t.get_rect(center=b.center))
        v=self.font.render(str(self.value),True,ACCENT); surf.blit(v,v.get_rect(center=self.rect.center))
    def handle(self,ev):
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.bd.collidepoint(ev.pos): self.value=max(self.mn,self.value-1)
            elif self.bi.collidepoint(ev.pos): self.value=min(self.mx,self.value+1)

class Slider:
    def __init__(self,rect,mn,mx,val,font,label):
        self.rect=pygame.Rect(rect); self.mn=mn; self.mx=mx; self.value=val; self.font=font; self.label=label; self.drag=False
    @property
    def kx(self):
        return self.rect.x+int((self.value-self.mn)/(self.mx-self.mn)*self.rect.width)
    def draw(self,surf):
        ty=self.rect.centery
        pygame.draw.line(surf,BORDER,(self.rect.x,ty),(self.rect.right,ty),2)
        pygame.draw.line(surf,ACCENT,(self.rect.x,ty),(self.kx,ty),2)
        pygame.draw.circle(surf,ACCENT,(self.kx,ty),7); pygame.draw.circle(surf,TEXT_PRI,(self.kx,ty),4)
        l=self.font.render(f"{self.label}: {int(self.value)}",True,TEXT_SEC)
        surf.blit(l,(self.rect.x,self.rect.y-13))
    def handle(self,ev):
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if math.hypot(ev.pos[0]-self.kx,ev.pos[1]-self.rect.centery)<12: self.drag=True
        if ev.type==pygame.MOUSEBUTTONUP: self.drag=False
        if ev.type==pygame.MOUSEMOTION and self.drag:
            t=(ev.pos[0]-self.rect.x)/self.rect.width
            self.value=self.mn+max(0.0,min(1.0,t))*(self.mx-self.mn)


class FitnessGraph:
    PAD=8
    def __init__(self,x,y,w,h,fsm,fxs):
        self.rect=pygame.Rect(x,y,w,h); self.fsm=fsm; self.fxs=fxs; self.history=[]
    def reset(self): self.history=[]
    def update(self,h): self.history=h
    def draw(self,surf):
        r=self.rect; p=self.PAD
        pygame.draw.rect(surf,GRAPH_BG,r,border_radius=5)
        pygame.draw.rect(surf,BORDER,r,1,border_radius=5)
        surf.blit(self.fsm.render("FITNESS PER GENERATION",True,TEXT_SEC),(r.x+p,r.y+3))
        lx,ly=r.right-180,r.y+3
        pygame.draw.line(surf,GRAPH_BEST,(lx,ly+5),(lx+12,ly+5),2)
        surf.blit(self.fxs.render("Best",True,GRAPH_BEST),(lx+15,ly))
        pygame.draw.line(surf,GRAPH_AVG,(lx+55,ly+5),(lx+67,ly+5),2)
        surf.blit(self.fxs.render("Avg",True,GRAPH_AVG),(lx+70,ly))
        if not self.history:
            m=self.fxs.render("Run GA to see fitness curve",True,TEXT_SEC)
            surf.blit(m,m.get_rect(center=r.center)); return
        px2=r.x+p+36; py2=r.y+18; pw2=r.width-p*2-40; ph2=r.height-30
        for i in range(5):
            gy=py2+int(i*ph2/4); pygame.draw.line(surf,GRAPH_GRID,(px2,gy),(px2+pw2,gy),1)
        n=len(self.history)
        ab=[h[0] for h in self.history]; aa=[h[1] for h in self.history]
        mx2=max(ab); mn2=min(aa); vr=max(mx2-mn2,1e-9)
        def ts(gi,v):
            sx=px2+int(gi/max(n-1,1)*pw2); sy=py2+ph2-int((v-mn2)/vr*ph2)
            return (sx,max(py2,min(py2+ph2,sy)))
        if n>=2:
            pb=[ts(i,v) for i,v in enumerate(ab)]; pa=[ts(i,v) for i,v in enumerate(aa)]
            fs=pygame.Surface((r.width,r.height),pygame.SRCALPHA)
            fp=[(px2-r.x,py2+ph2-r.y)]+[(fx-r.x,fy-r.y) for fx,fy in pb]+[(px2+pw2-r.x,py2+ph2-r.y)]
            pygame.draw.polygon(fs,(*GRAPH_BEST,18),fp); surf.blit(fs,(r.x,r.y))
            for i in range(1,n):
                pygame.draw.line(surf,GRAPH_AVG,pa[i-1],pa[i],1)
                pygame.draw.line(surf,GRAPH_BEST,pb[i-1],pb[i],2)
            lb=ts(n-1,ab[-1]); la=ts(n-1,aa[-1])
            surf.blit(self.fxs.render(f"{ab[-1]:.4f}",True,GRAPH_BEST),(lb[0]+3,lb[1]-8))
            surf.blit(self.fxs.render(f"{aa[-1]:.4f}",True,GRAPH_AVG),(la[0]+3,la[1]+2))
        for i in range(5):
            gy=py2+int(i*ph2/4); v=mx2-(mx2-mn2)*i/4
            surf.blit(self.fxs.render(f"{v:.3f}",True,TEXT_SEC),(r.x+2,gy-5))
        for i in range(6):
            gx=px2+int(i*pw2/5); gen=int(i*(n-1)/5)
            l=self.fxs.render(str(gen),True,TEXT_SEC); surf.blit(l,(gx-l.get_width()//2,py2+ph2+2))


class DemandInputScreen:
    def __init__(self,screen,customers,font_lg,font_md,font_sm,font_xs):
        self.screen=screen; self.customers=customers
        self.font_lg=font_lg; self.font_md=font_md; self.font_sm=font_sm; self.font_xs=font_xs
        self.demands=[c.demand for c in customers]
        self.active=0; self.input_str=str(self.demands[0])
        self.done=False; self.cancelled=False; self.scroll=0

    def _max_vis(self): return min(len(self.customers),(H-220)//34)
    def _vis(self): mv=self._max_vis(); return list(range(self.scroll,min(self.scroll+mv,len(self.customers))))
    def _commit(self):
        try:
            v=int(self.input_str)
            if v>=1: self.demands[self.active]=v
        except: pass
        self.input_str=str(self.demands[self.active])
    def _confirm_btn(self): return pygame.Rect(W//2-110,H-65,100,38)
    def _cancel_btn(self):  return pygame.Rect(W//2+10, H-65,100,38)

    def handle(self,ev):
        if ev.type==pygame.KEYDOWN:
            k=ev.key
            if k==pygame.K_ESCAPE: self.cancelled=True; return
            if k in(pygame.K_RETURN,pygame.K_KP_ENTER):
                self._commit()
                if self.active<len(self.customers)-1: self.active+=1; self.input_str=str(self.demands[self.active])
                else: self.done=True
                return
            if k==pygame.K_TAB:
                self._commit(); self.active=(self.active+1)%len(self.customers); self.input_str=str(self.demands[self.active]); return
            if k==pygame.K_UP:
                self._commit(); self.active=max(0,self.active-1); self.input_str=str(self.demands[self.active]); return
            if k==pygame.K_DOWN:
                self._commit(); self.active=min(len(self.customers)-1,self.active+1); self.input_str=str(self.demands[self.active]); return
            if k==pygame.K_BACKSPACE: self.input_str=self.input_str[:-1]; return
            if ev.unicode.isdigit(): self.input_str+=ev.unicode; return
        if ev.type==pygame.MOUSEWHEEL:
            mx=max(0,len(self.customers)-self._max_vis()); self.scroll=max(0,min(mx,self.scroll-ev.y))
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            mx,my=ev.pos
            if self._confirm_btn().collidepoint(mx,my): self._commit(); self.done=True; return
            if self._cancel_btn().collidepoint(mx,my):  self.cancelled=True; return
            for li,ci in enumerate(self._vis()):
                ry=155+li*34
                hx2=W//2-170
                mr=pygame.Rect(hx2,ry,28,28); pr=pygame.Rect(hx2+312,ry,28,28); row=pygame.Rect(hx2,ry,340,28)
                if mr.collidepoint(mx,my):
                    self._commit(); self.demands[ci]=max(1,self.demands[ci]-1); self.active=ci; self.input_str=str(self.demands[ci]); return
                if pr.collidepoint(mx,my):
                    self._commit(); self.demands[ci]+=1; self.active=ci; self.input_str=str(self.demands[ci]); return
                if row.collidepoint(mx,my):
                    self._commit(); self.active=ci; self.input_str=str(self.demands[ci]); return

    def draw(self):
        s=self.screen; s.fill((0,0,18))
        t=self.font_lg.render("CUSTOMER DEMANDS",True,TEXT_PRI); s.blit(t,t.get_rect(centerx=W//2,y=16))
        sub=self.font_xs.render("↑↓ navigate  |  type  |  ENTER next  |  scroll  |  ESC cancel",True,TEXT_SEC)
        s.blit(sub,sub.get_rect(centerx=W//2,y=46))
        pygame.draw.line(s,BORDER,(80,70),(W-80,70),1)
        hx=W//2-170
        s.blit(self.font_xs.render("Customer",True,ACCENT),(hx+36,118))
        s.blit(self.font_xs.render("Demand",True,ACCENT),(hx+236,118))
        pygame.draw.line(s,BORDER,(hx,135),(hx+340,135),1)
        hov=pygame.mouse.get_pos()
        for li,ci in enumerate(self._vis()):
            ry=155+li*34; col=VEHICLE_COLORS[ci%len(VEHICLE_COLORS)]; ia=(ci==self.active)
            pygame.draw.rect(s,(18,18,55) if ia else (5,5,28),(hx-4,ry-2,348,30),border_radius=4)
            if ia: pygame.draw.rect(s,BORDER,(hx-4,ry-2,348,30),1,border_radius=4)
            mr=pygame.Rect(hx,ry,28,28)
            pygame.draw.rect(s,BTN_HOV if mr.collidepoint(hov) else BTN_BG,mr,border_radius=4)
            pygame.draw.rect(s,BORDER,mr,1,border_radius=4)
            mt=self.font_md.render("−",True,TEXT_PRI); s.blit(mt,mt.get_rect(center=mr.center))
            pygame.draw.circle(s,col,(hx+40,ry+12),6)
            lbl=self.font_xs.render(f"Customer {ci+1:02d}",True,TEXT_PRI if ia else TEXT_SEC); s.blit(lbl,(hx+50,ry+6))
            disp=(self.input_str if ia else str(self.demands[ci]))+(("|" if ia and (pygame.time.get_ticks()//500)%2==0 else ""))
            dv=self.font_md.render(disp,True,ACCENT if ia else TEXT_PRI); s.blit(dv,dv.get_rect(centerx=hx+240,y=ry+5))
            pr=pygame.Rect(hx+312,ry,28,28)
            pygame.draw.rect(s,BTN_HOV if pr.collidepoint(hov) else BTN_BG,pr,border_radius=4)
            pygame.draw.rect(s,BORDER,pr,1,border_radius=4)
            pt=self.font_md.render("+",True,TEXT_PRI); s.blit(pt,pt.get_rect(center=pr.center))
        total=len(self.customers); mv=self._max_vis()
        if total>mv:
            sh=self.font_xs.render(f"{self.scroll+1}–{min(self.scroll+mv,total)} of {total}",True,TEXT_SEC)
            s.blit(sh,sh.get_rect(centerx=W//2,y=H-100))
        cb=self._confirm_btn(); cx2=self._cancel_btn()
        pygame.draw.rect(s,BTN_SOLVE_H if cb.collidepoint(hov) else BTN_SOLVE,cb,border_radius=6)
        pygame.draw.rect(s,BORDER,cb,1,border_radius=6)
        ct=self.font_md.render("CONFIRM",True,TEXT_PRI); s.blit(ct,ct.get_rect(center=cb.center))
        pygame.draw.rect(s,BTN_CLR_H if cx2.collidepoint(hov) else BTN_CLR,cx2,border_radius=6)
        pygame.draw.rect(s,BORDER,cx2,1,border_radius=6)
        cc=self.font_md.render("CANCEL",True,TEXT_PRI); s.blit(cc,cc.get_rect(center=cx2.center))


class VRPApp:
    def __init__(self):
        pygame.init()
        self.screen=pygame.display.set_mode((W,H))
        pygame.display.set_caption("PAC-VRP Solver")
        def pxfont(sz,bold=False):
            for nm in("Press Start 2P","Courier New","monospace"):
                try: return pygame.font.SysFont(nm,sz,bold=bold)
                except: pass
            return pygame.font.SysFont("monospace",sz,bold=bold)
        self.font_lg=pxfont(20,bold=True); self.font_md=pxfont(16)
        self.font_sm=pxfont(14);           self.font_xs=pxfont(13)

        self.sound=SoundManager()
        self.depot:Optional[Node]=None; self.customers:List[Node]=[]
        self.routes:List[Route]=[]; self.trucks:List[TruckAnim]=[]
        self.node_ctr=0; self.demands:List[int]=[]
        self.v_capacity=10; self.placing_depot=False
        self.dragging_node:Optional[Node]=None; self.drag_offset=(0,0)
        self.animating=False; self.paused=False
        self.status="Click canvas to add customers, or Randomize."
        self.route_revealed:List[float]=[]; self.fitness_history:List[Tuple[float,float]]=[]
        self.demand_screen:Optional[DemandInputScreen]=None
        self._init_widgets()
        gm=6
        self.fitness_graph=FitnessGraph(CANVAS_X+gm,GRAPH_Y+gm,CANVAS_W-gm*2,GRAPH_H-gm*2,self.font_sm,self.font_xs)
        self.clock=pygame.time.Clock()
        self.trail_surf=pygame.Surface((W,H),pygame.SRCALPHA)

    def _init_widgets(self):
        px=10; pw=PANEL_W-20; BH=32; GAP=6; y=82
        self._stats_y=y; y+=4*20+6; self._sep=[]; self._lbl_y={}

        self._sep.append(y); y+=GAP
        self._lbl_y['vehicles']=y; y+=16
        self.spin_vehicles=Spinbox((px,y,pw,BH),3,1,8,self.font_sm); y+=BH+GAP

        self._sep.append(y); y+=GAP
        self._lbl_y['capacity']=y; y+=16
        self.spin_capacity=Spinbox((px,y,pw,BH),10,1,999,self.font_sm); y+=BH+GAP

        self._sep.append(y); y+=GAP
        self._lbl_y['gens']=y; y+=16
        self.spin_gen=Spinbox((px,y,pw,BH),200,20,500,self.font_xs); y+=BH+GAP
        self._lbl_y['pop']=y; y+=16
        self.spin_pop=Spinbox((px,y,pw,BH),50,20,300,self.font_xs); y+=BH+GAP

        self._sep.append(y); y+=GAP
        self._lbl_y['rand_count']=y; y+=16
        self.spin_rand_count=Spinbox((px,y,pw,BH),15,3,50,self.font_xs); y+=BH+GAP

        self._sep.append(y); y+=GAP
        self._lbl_y['speed']=y; y+=16
        self.slider=Slider((px,y+16,pw,14),30,500,150.0,self.font_xs,"Speed px/s"); y+=16+14+GAP+4

        self._sep.append(y); y+=GAP
        self._lbl_y['actions']=y; y+=16
        hw=(pw-4)//2
        self.btn_depot   =Button((px,     y,hw,BH),"DEPOT",  BTN_BG,   BTN_HOV,   self.font_xs)
        self.btn_rand_all=Button((px+hw+4,y,hw,BH),"RANDOM", BTN_RAND, BTN_RAND_H,self.font_xs); y+=BH+GAP
        self.btn_solve   =Button((px,     y,hw,BH),"SOLVE",  BTN_SOLVE,BTN_SOLVE_H,self.font_xs)
        self.btn_clear   =Button((px+hw+4,y,hw,BH),"CLEAR",  BTN_CLR,  BTN_CLR_H, self.font_xs); y+=BH+GAP+4

        self._sep.append(y); y+=GAP
        self._routes_y=y

    def canvas_rect(self): return pygame.Rect(CANVAS_X,0,CANVAS_W,GRAPH_Y)

    def node_at(self,x,y)->Optional[Node]:
        for n in([self.depot]if self.depot else[])+self.customers:
            if n and math.hypot(n.x-x,n.y-y)<=NODE_R+5: return n
        return None

    def add_customer(self,x,y):
        self.customers.append(Node(x,y,self.node_ctr,demand=1))
        self.node_ctr+=1; self.routes=[]; self.trucks=[]; self.sound.play("click")

    def _rebuild_demands(self):
        self.demands=[0]+[c.demand for c in self.customers]

    def randomize_all(self):
        n=self.spin_rand_count.value; mg=50; x0,x1=CANVAS_X+mg,W-mg; y0,y1=mg,GRAPH_Y-mg
        self.customers.clear(); self.routes.clear(); self.trucks.clear()
        self.node_ctr=0; self.fitness_history=[]; self.fitness_graph.reset()
        cap=self.spin_capacity.value
        for _ in range(n):
            d=random.randint(1,max(1,cap//3))
            self.customers.append(Node(random.randint(x0,x1),random.randint(y0,y1),self.node_ctr,demand=d))
            self.node_ctr+=1
        dx,dy=x0,y0
        for _ in range(300):
            dx=random.randint(x0,x1); dy=random.randint(y0,y1)
            if all(math.hypot(dx-c.x,dy-c.y)>40 for c in self.customers): break
        self.depot=Node(dx,dy,-1); self._rebuild_demands(); self.sound.play("randomize")
        self.status=f"Randomised {n} customers. Press SOLVE."

    def solve(self):
        if not self.depot: self.status="Place a depot first!"; return
        if not self.customers: self.status="Add customers first."; return
        if not _LOGIC_OK: self.status="vrp_logic.py missing next to this file!"; return
        self._rebuild_demands()
        self.demand_screen=DemandInputScreen(self.screen,self.customers,self.font_lg,self.font_md,self.font_sm,self.font_xs)

    def _run_ga_after_demands(self):
        for i,c in enumerate(self.customers): c.demand=self.demand_screen.demands[i]
        self._rebuild_demands(); self.demand_screen=None
        self.v_capacity=self.spin_capacity.value
        n_vehicles=self.spin_vehicles.value
        total_d=sum(self.demands[1:])
        max_single=max(self.demands[1:])
        min_cap=max_single
        min_v=math.ceil(total_d/self.v_capacity)
        if self.v_capacity < min_cap:
            self.status=f"BLOCKED: Capacity {self.v_capacity} too low! Customer needs {min_cap}. Raise CAPACITY."
            return
        if n_vehicles < min_v:
            self.status=f"BLOCKED: {n_vehicles} truck(s) not enough. Need >={min_v} (demand {total_d} / cap {self.v_capacity}). Raise VEHICLES."
            return
        self.status="Running GA...  please wait."
        self.screen.fill(BG); self.draw_panel(self.screen); pygame.display.flip()
        self.sound.play("solve")
        self.routes,self.fitness_history=run_logic_ga(
            self.depot,self.customers,self.demands,
            n_vehicles,self.v_capacity,
            self.spin_pop.value,self.spin_gen.value)
        self.fitness_graph.update(self.fitness_history)
        total_k=sum(route_km(self.depot,r) for r in self.routes)
        bf=self.fitness_history[-1][0] if self.fitness_history else 0.0
        self.status=f"Done  |  {len(self.routes)} routes  |  {total_k:.2f}km  |  fit {bf:.4f}"
        self._start_animation()

    def _start_animation(self):
        self.trucks=[]
        for r in self.routes:
            col=VEHICLE_COLORS[r.vehicle_id%len(VEHICLE_COLORS)]
            tk=TruckAnim(route=r,waypoints=build_waypoints(self.depot,r),color=col)
            if not r.nodes: tk.done=True
            self.trucks.append(tk)
        self.route_revealed=[0.0]*len(self.routes)
        self.animating=True; self.paused=False

    def clear(self):
        self.depot=None; self.customers.clear(); self.routes.clear(); self.trucks.clear()
        self.node_ctr=0; self.animating=False; self.paused=False
        self.fitness_history=[]; self.fitness_graph.reset()
        self.demands=[]; self.demand_screen=None
        self.status="Canvas cleared."; self.sound.play("clear")

    def draw_grid(self,surf):
        for gx in range(CANVAS_X+20,W,40):
            for gy in range(20,GRAPH_Y,40):
                pygame.draw.circle(surf,(28,28,85),(gx,gy),1)

    def draw_routes_static(self,surf):
        if not self.routes or not self.depot: return
        s=pygame.Surface((W,H),pygame.SRCALPHA)
        for ri,r in enumerate(self.routes):
            col=VEHICLE_COLORS[r.vehicle_id%len(VEHICLE_COLORS)]
            wps=build_waypoints(self.depot,r)
            rev=self.route_revealed[ri] if ri<len(self.route_revealed) else 0.0
            for i in range(len(wps)-1):
                pygame.draw.line(s,(*col,22),(int(wps[i][0]),int(wps[i][1])),(int(wps[i+1][0]),int(wps[i+1][1])),1)
            dd=0.0
            for i in range(len(wps)-1):
                if dd>=rev: break
                ax,ay=wps[i]; bx,by=wps[i+1]; sl=math.hypot(bx-ax,by-ay)
                if dd+sl<=rev:
                    pygame.draw.line(s,(*col,ROUTE_ALPHA),(int(ax),int(ay)),(int(bx),int(by)),2)
                    if sl>20:
                        mx2,my2=(ax+bx)/2,(ay+by)/2; ux,uy=(bx-ax)/sl,(by-ay)/sl
                        a1=(mx2-ux*8-uy*4,my2-uy*8+ux*4); a2=(mx2-ux*8+uy*4,my2-uy*8-ux*4)
                        pygame.draw.polygon(s,(*col,180),[(int(mx2),int(my2)),(int(a1[0]),int(a1[1])),(int(a2[0]),int(a2[1]))])
                    dd+=sl
                else:
                    f=(rev-dd)/max(sl,0.001); ex,ey=ax+(bx-ax)*f,ay+(by-ay)*f
                    pygame.draw.line(s,(*col,ROUTE_ALPHA),(int(ax),int(ay)),(int(ex),int(ey)),2); break
        surf.blit(s,(0,0))

    def draw_trails(self,surf):
        s=self.trail_surf; s.fill((0,0,0,0))
        for tk in self.trucks:
            tl=tk.trail
            if len(tl)<2: continue
            n=len(tl)
            for i in range(1,n):
                pygame.draw.line(s,(*tk.color,int(150*i/n)),(int(tl[i-1][0]),int(tl[i-1][1])),(int(tl[i][0]),int(tl[i][1])),max(1,int(4*i/n)))
        surf.blit(s,(0,0))

    def draw_nodes(self,surf):
        af={}
        for tk in self.trucks:
            for ni,t in tk.flash_timers.items(): af[ni]=max(af.get(ni,0.0),t)
        for n in self.customers:
            vis=any(n.idx in t.visited for t in self.trucks); fl=af.get(n.idx,0.0)
            if fl>0.0:
                fr2=fl/0.5; fa=int(255*fr2); fr=int(NODE_R+14*(1.0-fr2))
                fs=pygame.Surface((fr*4,fr*4),pygame.SRCALPHA)
                pygame.draw.circle(fs,(255,255,0,fa),(fr*2,fr*2),fr,2)
                surf.blit(fs,(int(n.x)-fr*2,int(n.y)-fr*2))
            if not vis:
                pygame.draw.circle(surf,(210,210,170),(int(n.x),int(n.y)),5)
                pygame.draw.circle(surf,(255,255,200),(int(n.x),int(n.y)),3)
            else:
                pygame.draw.circle(surf,(55,55,25),(int(n.x),int(n.y)),5,1)
            it=self.font_xs.render(f"{n.idx}|{n.demand}",True,(255,255,0) if not vis else (70,70,35))
            surf.blit(it,it.get_rect(center=(int(n.x),int(n.y)-13)))
        if self.depot:
            d=self.depot; t2=pygame.time.get_ticks()/1000.0
            pulse=int(DEPOT_R+2.5*abs(math.sin(t2*2.5)))
            gs=pygame.Surface((pulse*4,pulse*4),pygame.SRCALPHA)
            pygame.draw.circle(gs,(255,255,0,50),(pulse*2,pulse*2),pulse*2)
            surf.blit(gs,(int(d.x)-pulse*2,int(d.y)-pulse*2))
            pygame.draw.circle(surf,(0,0,0),(int(d.x),int(d.y)),pulse+2)
            pygame.draw.circle(surf,DEPOT_COL,(int(d.x),int(d.y)),pulse)
            pygame.draw.circle(surf,(255,255,180),(int(d.x),int(d.y)),pulse//2)
            dt2=self.font_xs.render("D",True,(0,0,0)); surf.blit(dt2,dt2.get_rect(center=(int(d.x),int(d.y))))

    def draw_trucks(self,surf):
        for tk in self.trucks:
            if tk.done: continue
            px2,py2=tk.current_pos(); draw_truck(surf,px2,py2,tk.current_angle(),tk.color)
            v=self.font_xs.render(f"V{tk.route.vehicle_id+1}",True,(255,255,0))
            surf.blit(v,(int(px2)+14,int(py2)-14))

    def draw_panel(self,surf):
        pygame.draw.rect(surf,PANEL_BG,(0,0,PANEL_W,H))
        pygame.draw.line(surf,BORDER,(PANEL_W,0),(PANEL_W,H),2)
        surf.blit(self.font_lg.render("PAC-VRP",True,TEXT_PRI),(10,8))
        mute_col=ACCENT if self.sound._enabled else (160,50,50)
        surf.blit(self.font_xs.render("M:mute" if self.sound._enabled else "M:unmute",True,mute_col),(10,32))
        lc=(0,200,70) if _LOGIC_OK else (220,60,60)
        surf.blit(self.font_xs.render("logic:ok" if _LOGIC_OK else "logic:MISS",True,lc),(10,46))
        pygame.draw.line(surf,BORDER,(8,62),(PANEL_W-8,62),1)
        all_done=bool(self.trucks) and all(t.done for t in self.trucks)
        anim_str="DONE!" if all_done else("PAUSED" if self.paused else("RUNNING" if self.animating else "IDLE"))
        anim_col=(80,220,100) if all_done else(ACCENT if self.animating and not self.paused else TEXT_PRI)
        y=self._stats_y
        for lbl,val,vc in[("DEPOT","YES" if self.depot else "NO",TEXT_PRI),
                           ("NODES",str(len(self.customers)),TEXT_PRI),
                           ("ROUTES",str(len(self.routes)),TEXT_PRI),
                           ("STATE",anim_str,anim_col)]:
            surf.blit(self.font_xs.render(lbl,True,TEXT_SEC),(10,y))
            vt=self.font_xs.render(val,True,vc); surf.blit(vt,(PANEL_W-10-vt.get_width(),y)); y+=20
        for sy in self._sep: pygame.draw.line(surf,BORDER,(8,sy),(PANEL_W-8,sy),1)
        surf.blit(self.font_xs.render("VEHICLES",True,TEXT_SEC),(10,self._lbl_y['vehicles']))
        self.spin_vehicles.draw(surf)
        surf.blit(self.font_xs.render("CAPACITY",True,TEXT_SEC),(10,self._lbl_y['capacity']))
        self.spin_capacity.draw(surf)
        surf.blit(self.font_xs.render("GENERATIONS",True,TEXT_SEC),(10,self._lbl_y['gens']))
        self.spin_gen.draw(surf)
        surf.blit(self.font_xs.render("POPULATION",True,TEXT_SEC),(10,self._lbl_y['pop']))
        self.spin_pop.draw(surf)
        surf.blit(self.font_xs.render("RAND COUNT",True,TEXT_SEC),(10,self._lbl_y['rand_count']))
        self.spin_rand_count.draw(surf)
        surf.blit(self.font_xs.render("ANIM SPEED",True,TEXT_SEC),(10,self._lbl_y['speed']))
        self.slider.draw(surf)
        surf.blit(self.font_xs.render("ACTIONS",True,TEXT_SEC),(10,self._lbl_y['actions']))
        self.btn_depot.draw(surf); self.btn_rand_all.draw(surf)
        self.btn_solve.draw(surf); self.btn_clear.draw(surf)
        ROUTE_SECTION_H = 170
        route_top = H - ROUTE_SECTION_H
        pygame.draw.line(surf,BORDER,(8,route_top),(PANEL_W-8,route_top),1)
        surf.blit(self.font_xs.render("ROUTES  (km)",True,TEXT_SEC),(10,route_top+4))
        if self.routes and self.depot:
            max_show=min(len(self.routes),6)
            for i,r in enumerate(self.routes[:max_show]):
                col=VEHICLE_COLORS[r.vehicle_id%len(VEHICLE_COLORS)]
                ry=route_top+20+i*22
                pygame.draw.circle(surf,col,(18,ry+7),5)
                tk=next((t for t in self.trucks if t.route.vehicle_id==r.vehicle_id),None)
                done_mark="✓" if tk and tk.done else " "
                km=route_km(self.depot,r)
                total_d=sum(r.nodes[j].demand for j in range(len(r.nodes)))
                txt=f"V{r.vehicle_id+1} {done_mark}  {len(r.nodes)}stops  {km:.2f}km  d:{total_d}"
                info=self.font_xs.render(txt,True,col if(tk and tk.done) else TEXT_PRI)
                surf.blit(info,(28,ry))
        else:
            nh=self.font_xs.render("No routes yet",True,TEXT_SEC)
            surf.blit(nh,(10,route_top+22))
        pygame.draw.line(surf,BORDER,(8,H-38),(PANEL_W-8,H-38),1)
        words=self.status.split(); ln=""; lines=[]
        for w in words:
            t=(ln+" "+w).strip()
            if self.font_xs.size(t)[0]>PANEL_W-18: lines.append(ln); ln=w
            else: ln=t
        if ln: lines.append(ln)
        for i,l in enumerate(lines[:2]):
            surf.blit(self.font_xs.render(l,True,TEXT_PRI),(10,H-33+i*14))

    def draw_cursor_hint(self,surf):
        if self.placing_depot:
            mx,my=pygame.mouse.get_pos()
            if self.canvas_rect().collidepoint(mx,my):
                s=pygame.Surface((DEPOT_R*4,DEPOT_R*4),pygame.SRCALPHA)
                pygame.draw.circle(s,(*DEPOT_COL,90),(DEPOT_R*2,DEPOT_R*2),DEPOT_R,2)
                surf.blit(s,(mx-DEPOT_R*2,my-DEPOT_R*2))
                ht=self.font_xs.render("click to place depot",True,DEPOT_COL)
                surf.blit(ht,(mx+14,my-6))

    def update_animation(self,dt):
        if not self.animating or self.paused: return
        speed=self.slider.value; all_done=True
        for ti,tk in enumerate(self.trucks):
            if tk.done: continue
            all_done=False; prev=set(tk.visited)
            tk.advance(dt,speed)
            for _ in tk.visited-prev: self.sound.play("waka")
            for k in list(tk.flash_timers):
                tk.flash_timers[k]-=dt
                if tk.flash_timers[k]<=0: del tk.flash_timers[k]
            if ti<len(self.route_revealed):
                wps=tk.waypoints; seg=tk.seg_idx
                rev=sum(math.hypot(wps[i+1][0]-wps[i][0],wps[i+1][1]-wps[i][1]) for i in range(min(seg,len(wps)-1)))
                if seg<len(wps)-1:
                    sl=math.hypot(wps[seg+1][0]-wps[seg][0],wps[seg+1][1]-wps[seg][1]); rev+=sl*tk.seg_t
                self.route_revealed[ti]=rev
        if all_done and self.trucks:
            self.animating=False
            for ti,r in enumerate(self.routes): self.route_revealed[ti]=total_route_distance(self.depot,r)
            self.status="All trucks returned to depot!"; self.sound.play("victory")

    def run(self):
        running=True
        while running:
            dt=min(self.clock.tick(60)/1000.0,0.05)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: running=False
                if self.demand_screen is not None:
                    self.demand_screen.handle(ev)
                    if self.demand_screen.cancelled: self.demand_screen=None; self.status="Solve cancelled."
                    elif self.demand_screen.done: self._run_ga_after_demands()
                    continue
                self.spin_vehicles.handle(ev); self.spin_capacity.handle(ev)
                self.spin_gen.handle(ev); self.spin_pop.handle(ev)
                self.spin_rand_count.handle(ev); self.slider.handle(ev)
                if self.btn_depot.clicked(ev): self.placing_depot=True; self.status="Click canvas to place depot."
                if self.btn_rand_all.clicked(ev): self.randomize_all()
                if self.btn_solve.clicked(ev): self.solve()
                if self.btn_clear.clicked(ev): self.clear()
                if ev.type==pygame.MOUSEBUTTONDOWN:
                    mx,my=ev.pos; oc=self.canvas_rect().collidepoint(mx,my)
                    if oc and ev.button==1:
                        if self.placing_depot:
                            self.depot=Node(mx,my,-1); self.placing_depot=False
                            self.routes=[]; self.trucks=[]; self.status="Depot placed. Press SOLVE."
                            self.sound.play("depot")
                        else:
                            hit=self.node_at(mx,my)
                            if hit: self.dragging_node=hit; self.drag_offset=(hit.x-mx,hit.y-my)
                            elif not self.animating: self.add_customer(mx,my); self.status=f"Added node #{self.node_ctr-1}."
                    elif oc and ev.button==3 and not self.animating:
                        hit=self.node_at(mx,my)
                        if hit:
                            if hit is self.depot: self.depot=None; self.routes=[]; self.trucks=[]; self.status="Depot removed."
                            else: self.customers.remove(hit); self.routes=[]; self.trucks=[]; self.status=f"Removed node #{hit.idx}."
                if ev.type==pygame.MOUSEBUTTONUP and ev.button==1: self.dragging_node=None
                if ev.type==pygame.MOUSEMOTION and self.dragging_node and not self.animating:
                    mx2,my2=ev.pos
                    self.dragging_node.x=mx2+self.drag_offset[0]; self.dragging_node.y=my2+self.drag_offset[1]
                    self.routes=[]; self.trucks=[]; self.status="Node moved — re-solve."
                if ev.type==pygame.KEYDOWN:
                    if ev.key==pygame.K_ESCAPE: self.placing_depot=False
                    elif ev.key==pygame.K_RETURN: self.solve()
                    elif ev.key in(pygame.K_DELETE,pygame.K_BACKSPACE): self.clear()
                    elif ev.key==pygame.K_SPACE:
                        if self.animating or self.paused: self.paused=not self.paused
                    elif ev.key==pygame.K_r: self.randomize_all()
                    elif ev.key==pygame.K_m:
                        on=self.sound.toggle()
                        self.status=f"Sound {'ON' if on else 'MUTED'}"

            self.update_animation(dt)
            self.screen.fill(BG)
            if self.demand_screen is not None:
                self.demand_screen.draw()
            else:
                self.draw_grid(self.screen)
                pygame.draw.rect(self.screen,BORDER,pygame.Rect(CANVAS_X,0,CANVAS_W,GRAPH_Y),2,border_radius=3)
                self.draw_routes_static(self.screen)
                self.draw_trails(self.screen)
                self.draw_nodes(self.screen)
                self.draw_trucks(self.screen)
                pygame.draw.line(self.screen,BORDER,(CANVAS_X,GRAPH_Y),(W,GRAPH_Y),2)
                self.fitness_graph.draw(self.screen)
                self.draw_panel(self.screen)
                self.draw_cursor_hint(self.screen)
            pygame.display.flip()
        pygame.quit()

if __name__=="__main__":
    VRPApp().run()
