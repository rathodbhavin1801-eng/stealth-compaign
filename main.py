import pygame, math, random, heapq, json, os, sys, time, struct

# ============================================================
# stealth campaign- COMPLETE 2D STEALTH ACTION GAME
# Controls:
# WASD/Arrows = move | Shift = sprint | C ou = crouch
# F / Left Mouse = attack | Space = dash | ESC = pause
# R = restart | M = menu
# ============================================================

WIDTH, HEIGHT = 1100, 720
FPS = 60
CELL = 20
# Keep save data beside this script so progress persists even when the game is
# launched from a different working directory (VS Code, shortcut, terminal, etc.).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(BASE_DIR, "save.json")
LEVEL_DIR = os.path.join(BASE_DIR, "levels")

BG = (18, 20, 28)
GRID = (30, 33, 44)
WALL = (62, 66, 82)
WALL_TOP = (95, 100, 120)
PLAYER = (50, 235, 190)
ENEMY = (235, 65, 75)
ELITE = (255, 155, 55)
BOSS = (190, 75, 255)
TARGET = (255, 205, 55)
WHITE = (245, 248, 255)
MUTED = (155, 165, 180)
GREEN = (60, 230, 130)
RED = (240, 65, 75)
YELLOW = (255, 210, 60)
BLUE = (70, 170, 255)

# ============================================================
# PLAYER SKINS
# Purchased with coins and saved permanently in save.json.
# No external image assets are required.
# ============================================================
SKINS = {
    "default": {"name": "CYBER", "cost": 0, "color": PLAYER, "accent": WHITE},
    "crimson": {"name": "CRIMSON", "cost": 150, "color": (235, 55, 70), "accent": (255, 190, 190)},
    "shadow": {"name": "SHADOW", "cost": 250, "color": (75, 78, 92), "accent": (185, 195, 215)},
    "gold": {"name": "GOLD", "cost": 400, "color": (240, 175, 45), "accent": (255, 235, 150)},
    "toxic": {"name": "TOXIC", "cost": 550, "color": (80, 225, 105), "accent": (210, 255, 215)},
    "plasma": {"name": "PLASMA", "cost": 750, "color": (170, 75, 255), "accent": (235, 200, 255)},
    "ice": {"name": "ICE", "cost": 950, "color": (80, 200, 255), "accent": (220, 250, 255)},
}

def clamp(v, a, b): return max(a, min(b, v))

def dist(a,b): return math.hypot(b[0]-a[0], b[1]-a[1])

def angle_diff(a,b):
    return (a-b+math.pi) % (2*math.pi) - math.pi

class SoundManager:
    """Procedural sound effects and a seamless looping background soundtrack."""
    def __init__(self, enabled=True):
        self.enabled=bool(enabled); self.available=False; self.sounds={}
        self.music=None; self.music_channel=None
        try:
            if pygame.mixer.get_init():
                self._build_sounds()
                self._build_music()
        except pygame.error:
            pass
        self.set_enabled(enabled)
    def _tone(self, freqs, duration, volume=.2):
        init=pygame.mixer.get_init()
        if not init or abs(init[1])!=16: return None
        rate,fmt,channels=init; n=max(1,int(rate*duration)); out=bytearray()
        for i in range(n):
            t=i/rate
            env=min(1,i/max(1,int(rate*.008)))*min(1,(n-i)/max(1,int(rate*.035)))
            v=sum(math.sin(math.tau*f*t) for f in freqs)/len(freqs)
            sample=int(32767*volume*env*v); out.extend(struct.pack("<h",sample)*channels)
        try:return pygame.mixer.Sound(buffer=bytes(out))
        except pygame.error:return None
    def _build_sounds(self):
        self.sounds={"click":self._tone((520,780),.055,.18),"kill":self._tone((180,90),.16,.24),"detect":self._tone((760,980),.18,.20),"complete":self._tone((523,659,784,1047),.42,.20),"coin":self._tone((880,1320),.11,.17)}
        self.available=any(self.sounds.values())
    def _build_music(self):
        """Create an original, quiet sci-fi synth loop without external files."""
        init=pygame.mixer.get_init()
        if not init or abs(init[1])!=16:
            return
        rate,fmt,channels=init
        duration=8.0
        count=int(rate*duration)
        melody=(220.00,261.63,293.66,349.23,293.66,261.63,196.00,220.00,
                220.00,261.63,329.63,349.23,392.00,349.23,293.66,261.63)
        roots=(55.00,65.41,73.42,49.00)
        out=bytearray()
        for i in range(count):
            t=i/rate
            beat=int(t/0.5)%len(melody)
            local=t%0.5
            # Soft plucked lead with a gentle attack/decay.
            env=min(1.0,local/0.025)*math.exp(-local*2.8)
            lead=math.sin(math.tau*melody[beat]*t)*env*0.22
            # Low pulsing bass and two quiet sustained synth tones.
            root=roots[int(t/2.0)%len(roots)]
            bass=math.sin(math.tau*root*t)*0.20
            pad=(math.sin(math.tau*(root*2.0)*t)*0.09+
                 math.sin(math.tau*(root*3.0)*t)*0.045)
            # Tiny fade at the loop seam prevents an audible click.
            fade=min(1.0,t/0.035,(duration-t)/0.035)
            sample=int(32767*0.20*(lead+bass+pad)*max(0.0,fade))
            packed=struct.pack("<h",max(-32767,min(32767,sample)))
            out.extend(packed*channels)
        try:
            self.music=pygame.mixer.Sound(buffer=bytes(out))
            self.music.set_volume(0.32)
        except pygame.error:
            self.music=None
    def play(self,name):
        if self.enabled and self.available and self.sounds.get(name):
            try:self.sounds[name].play()
            except pygame.error:pass
    def set_enabled(self,enabled):
        self.enabled=bool(enabled)
        try:
            if not self.enabled:
                if self.music_channel:
                    self.music_channel.stop()
                    self.music_channel=None
            elif self.music and (not self.music_channel or not self.music_channel.get_busy()):
                self.music_channel=self.music.play(loops=-1)
        except pygame.error:
            self.music_channel=None

class Particle:
    def __init__(self,x,y,color,lifetime=35,speed=4,size=4):
        self.x,self.y=x,y
        a=random.random()*math.tau
        s=random.uniform(.5,speed)
        self.vx,self.vy=math.cos(a)*s,math.sin(a)*s
        self.life=self.max_life=random.randint(max(5,lifetime-10),lifetime+10)
        self.color=color
        self.size=size
    def update(self):
        self.x+=self.vx; self.y+=self.vy
        self.vx*=.94; self.vy*=.94
        self.life-=1
    def draw(self,s):
        if self.life<=0:return
        a=int(255*self.life/self.max_life)
        surf=pygame.Surface((self.size*2+2,self.size*2+2),pygame.SRCALPHA)
        pygame.draw.circle(surf,(*self.color,a),(self.size+1,self.size+1),self.size)
        s.blit(surf,(self.x-self.size-1,self.y-self.size-1))

class Wall:
    def __init__(self,x,y,w,h):
        self.rect=pygame.Rect(x,y,w,h)
    def draw(self,s):
        shadow=self.rect.move(0,7)
        pygame.draw.rect(s,(10,11,15),shadow,border_radius=3)
        pygame.draw.rect(s,WALL,self.rect,border_radius=3)
        pygame.draw.rect(s,WALL_TOP,(self.rect.x,self.rect.y,self.rect.w,4),border_radius=2)

class Gem:
    def __init__(self,x,y):
        # FIXED COIN POSITION:
        # Store one immutable world-space anchor. The coin is never moved,
        # bobbed, shaken, or recalculated from time. The collision rectangle
        # is rebuilt from the same anchor so visual and collision positions
        # always stay together.
        self.anchor_x = int(x)
        self.anchor_y = int(y)
        self.rect = pygame.Rect(0, 0, 16, 16)
        self.rect.center = (self.anchor_x, self.anchor_y)
        self.collected = False

    def draw(self,s,t=0):
        if self.collected:
            return

        # Force the exact original position every frame.
        # There is intentionally NO sine animation or random movement.
        self.rect.center = (self.anchor_x, self.anchor_y)
        cx, cy = self.anchor_x, self.anchor_y
        pts = [(cx, cy-9),
               (cx+8, cy),
               (cx, cy+9),
               (cx-8, cy)]
        pygame.draw.polygon(s, (0,235,255), pts)
        pygame.draw.polygon(s, WHITE, pts, 1)

class Pathfinder:
    def __init__(self,walls):
        self.cols=WIDTH//CELL; self.rows=HEIGHT//CELL
        self.grid=[[True for _ in range(self.rows)] for _ in range(self.cols)]
        for w in walls:
            r=w.rect.inflate(22,22)
            for x in range(max(0,r.left//CELL),min(self.cols-1,r.right//CELL)+1):
                for y in range(max(0,r.top//CELL),min(self.rows-1,r.bottom//CELL)+1):
                    self.grid[x][y]=False
    def path(self,start,end):
        a=(int(start[0]//CELL),int(start[1]//CELL))
        b=(int(end[0]//CELL),int(end[1]//CELL))
        if not (0<=a[0]<self.cols and 0<=a[1]<self.rows):return []
        if not (0<=b[0]<self.cols and 0<=b[1]<self.rows):return []
        if not self.grid[a[0]][a[1]]: return []
        if not self.grid[b[0]][b[1]]:
            found=None
            for r in range(1,6):
                for dx in range(-r,r+1):
                    for dy in range(-r,r+1):
                        q=(b[0]+dx,b[1]+dy)
                        if 0<=q[0]<self.cols and 0<=q[1]<self.rows and self.grid[q[0]][q[1]]:
                            found=q; break
                    if found:break
                if found:break
            if not found:return []
            b=found
        neigh=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]
        heap=[(0,a)]; came={}; g={a:0}; seen=set()
        while heap:
            _,cur=heapq.heappop(heap)
            if cur in seen:continue
            seen.add(cur)
            if cur==b:
                out=[]
                while cur!=a:
                    out.append(cur);cur=came[cur]
                return out[::-1]
            for dx,dy in neigh:
                n=(cur[0]+dx,cur[1]+dy)
                if not(0<=n[0]<self.cols and 0<=n[1]<self.rows) or not self.grid[n[0]][n[1]]:continue
                if dx and dy and (not self.grid[cur[0]+dx][cur[1]] or not self.grid[cur[0]][cur[1]+dy]):continue
                ng=g[cur]+(1.414 if dx and dy else 1)
                if ng<g.get(n,1e9):
                    g[n]=ng; came[n]=cur
                    h=math.hypot(n[0]-b[0],n[1]-b[1])
                    heapq.heappush(heap,(ng+h,n))
        return []

class Player:
    def __init__(self,pos):
        self.rect=pygame.Rect(0,0,24,24); self.rect.center=pos
        self.x,self.y=map(float,self.rect.topleft)
        self.angle=0
        self.health=self.max_health=100
        self.armor=self.max_armor=25
        self.stamina=self.max_stamina=100
        self.attack_cd=0; self.attack_timer=0
        self.dash_cd=0; self.dash_timer=0
        self.invuln=0; self.alive=True
        self.crouching=False; self.sprinting=False
        self.target=None
        self.anim=0
        self.skin="default"
    def center(self):return self.rect.center
    def move(self,dx,dy,walls):
        if not self.alive:return
        if dx and dy:
            dx*=.7071;dy*=.7071
        self.x+=dx; self.rect.x=int(self.x)
        for w in walls:
            if self.rect.colliderect(w.rect):
                if dx>0:self.rect.right=w.rect.left
                elif dx<0:self.rect.left=w.rect.right
                self.x=float(self.rect.x)
        self.y+=dy; self.rect.y=int(self.y)
        for w in walls:
            if self.rect.colliderect(w.rect):
                if dy>0:self.rect.bottom=w.rect.top
                elif dy<0:self.rect.top=w.rect.bottom
                self.y=float(self.rect.y)
        if dx or dy:self.angle=math.atan2(dy,dx)
    def take_damage(self,dmg):
        if self.invuln or not self.alive:return False
        absorbed=min(self.armor,dmg*.55); self.armor-=absorbed
        dmg-=absorbed; self.health-=dmg
        self.invuln=25
        if self.health<=0:self.health=0;self.alive=False
        return True
    def attack(self,enemies,particles):
        if not self.alive or self.attack_cd>0:return None
        self.attack_cd=42; self.attack_timer=14
        best=None; bestd=66
        for e in enemies:
            if e.dead:continue
            d=dist(self.center(),e.center())
            if d>66:continue
            a=math.atan2(e.rect.centery-self.rect.centery,e.rect.centerx-self.rect.centerx)
            if abs(angle_diff(a,self.angle))<math.radians(70) and d<bestd:
                best,bestd=e,d
        if best:
            best.take_damage(100,particles)
            self.target=best
            return best
        return None
    def dash(self,walls):
        if self.dash_cd>0 or not self.alive:return False
        self.dash_cd=120;self.dash_timer=8
        return True
    def update(self):
        for a in ("attack_cd","dash_cd","invuln","attack_timer","dash_timer"):
            v=getattr(self,a)
            if v>0:setattr(self,a,v-1)
        self.anim+=1
        self.stamina=min(self.max_stamina,self.stamina+.45)
    def draw(self,s):
        if not self.alive:
            pygame.draw.circle(s,(100,30,35),self.center(),13);return
        skin=SKINS.get(self.skin,SKINS["default"])
        c=skin["color"] if not self.invuln%4 else WHITE
        accent=skin["accent"]
        r=13 if not self.crouching else 10

        # Robot body + core + directional visor. The selected skin changes
        # the robot's body and accent colors without needing image files.
        pygame.draw.circle(s,(8,10,15),self.center(),r+3)
        pygame.draw.circle(s,c,self.center(),r)
        pygame.draw.circle(s,accent,self.center(),max(3,r//3))
        tip=(self.rect.centerx+math.cos(self.angle)*18,
             self.rect.centery+math.sin(self.angle)*18)
        pygame.draw.line(s,accent,self.center(),tip,3)
        if self.attack_timer:
            p=(self.rect.centerx+math.cos(self.angle)*38,
               self.rect.centery+math.sin(self.angle)*38)
            pygame.draw.circle(s,YELLOW,p,10,3)

class Enemy:
    TYPES={
        "guard":{"speed":1.45,"vision":270,"fov":72,"health":60,"damage":8,"color":ENEMY},
        "elite":{"speed":1.8,"vision":320,"fov":82,"health":100,"damage":12,"color":ELITE},
        "boss":{"speed":1.55,"vision":370,"fov":95,"health":180,"damage":18,"color":BOSS},
        "target":{"speed":1.25,"vision":300,"fov":75,"health":120,"damage":10,"color":TARGET},
    }
    def __init__(self,kind,waypoints,position=None):
        cfg=self.TYPES.get(kind,self.TYPES["guard"])
        self.kind=kind;self.waypoints=waypoints or [position or (500,300)]
        self.x,self.y=map(float,position or self.waypoints[0])
        self.rect=pygame.Rect(0,0,25,25);self.rect.center=(self.x,self.y)
        self.angle=0;self.wp=0
        self.speed=cfg["speed"];self.vision=cfg["vision"];self.fov=math.radians(cfg["fov"])
        self.max_health=cfg["health"];self.health=self.max_health;self.damage=cfg["damage"]
        self.color=cfg["color"];self.state="PATROL";self.alert=0
        self.last_known=None;self.search_timer=0;self.attack_cd=0;self.dead=False
        self.path=[];self.path_i=0;self.particles=[];self.was_visible=False
    def center(self):return self.rect.center
    def take_damage(self,dmg,particles):
        if self.dead:return
        self.health-=dmg
        for _ in range(8):particles.append(Particle(*self.center(),self.color,25,3,3))
        if self.health<=0:
            self.dead=True;self.state="DEAD"
            for _ in range(28):particles.append(Particle(*self.center(),(190,30,35),45,5,4))
    def sees(self,player,walls):
        if self.dead or not player.alive:return False
        d=dist(self.center(),player.center())
        if d>self.vision:return False
        a=math.atan2(player.rect.centery-self.rect.centery,player.rect.centerx-self.rect.centerx)
        if abs(angle_diff(a,self.angle))>self.fov/2:return False
        return not any(w.rect.clipline(self.center(),player.center()) for w in walls)
    def hears(self,pos,noise,walls):
        if self.dead:return False
        d=dist(self.center(),pos)
        if d>noise:return False
        # Hearing can be reduced by walls.
        blocked=sum(1 for w in walls if w.rect.clipline(self.center(),pos))
        return d <= noise/(1+blocked*.35)
    def update(self,player,walls,pathfinder,noise_events,particles):
        if self.dead:return
        self.attack_cd=max(0,self.attack_cd-1)
        visible=self.sees(player,walls)
        heard=any(self.hears(p,r,walls) for p,r in noise_events)
        if visible:
            self.state="CHASE";self.alert=min(100,self.alert+5);self.last_known=player.center()
        elif heard and self.state not in ("CHASE","ATTACK"):
            self.state="SUSPICIOUS";self.alert=min(100,self.alert+8)
            nearest=min(noise_events,key=lambda x:dist(self.center(),x[0]))
            self.last_known=nearest[0];self.search_timer=180
        elif self.state=="CHASE":
            self.state="SEARCH";self.search_timer=240
        elif self.state=="SUSPICIOUS":
            self.search_timer-=1
            if self.search_timer<=0:self.state="PATROL";self.alert=max(0,self.alert-2)
        elif self.state=="SEARCH":
            self.search_timer-=1
            if self.search_timer<=0:self.state="PATROL";self.alert=max(0,self.alert-2)
        if self.state in ("CHASE","SEARCH","SUSPICIOUS"):
            target=player.center() if self.state=="CHASE" else self.last_known
            if target:
                if not self.path or self.path_i>=len(self.path) or random.random()<.025:
                    self.path=pathfinder.path(self.center(),target);self.path_i=0
                if self.path and self.path_i<len(self.path):
                    tx=self.path[self.path_i][0]*CELL+CELL/2
                    ty=self.path[self.path_i][1]*CELL+CELL/2
                    a=math.atan2(ty-self.y,tx-self.x);self.angle=a
                    step=self.speed*(1.2 if self.state=="CHASE" else .85)
                    self.x+=math.cos(a)*step;self.y+=math.sin(a)*step
                    if math.hypot(tx-self.x,ty-self.y)<step+2:self.path_i+=1
        else:
            target=self.waypoints[self.wp]
            d=dist((self.x,self.y),target)
            if d<self.speed:
                self.x,self.y=map(float,target);self.wp=(self.wp+1)%len(self.waypoints)
            else:
                self.angle=math.atan2(target[1]-self.y,target[0]-self.x)
                self.x+=math.cos(self.angle)*self.speed;self.y+=math.sin(self.angle)*self.speed
        self.rect.center=(int(self.x),int(self.y))
        if visible and dist(self.center(),player.center())<42 and self.attack_cd==0:
            if player.take_damage(self.damage):
                self.attack_cd=60
                for _ in range(10):particles.append(Particle(*player.center(),RED,25,4,3))
    def draw_vision(self,s,walls):
        if self.dead:return
        poly=[self.center()]
        for i in range(41):
            a=self.angle-self.fov/2+i/40*self.fov
            end=(self.rect.centerx+math.cos(a)*self.vision,self.rect.centery+math.sin(a)*self.vision)
            hit=end
            closest=self.vision
            for w in walls:
                clip=w.rect.clipline(self.center(),end)
                if clip:
                    for p in clip:
                        d=dist(self.center(),p)
                        if d<closest:closest=d;hit=p
            poly.append(hit)
        col=(255,70,70,60) if self.state in ("CHASE","ATTACK") else (255,220,80,32)
        ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA);pygame.draw.polygon(ov,col,poly);s.blit(ov,(0,0))
    def draw(self,s):
        if self.dead:
            pygame.draw.circle(s,(95,35,40),self.center(),12);return
        pygame.draw.circle(s,self.color,self.center(),13)
        tip=(self.rect.centerx+math.cos(self.angle)*17,self.rect.centery+math.sin(self.angle)*17)
        pygame.draw.line(s,WHITE,self.center(),tip,2)
        if self.state in ("SUSPICIOUS","CHASE"):
            pygame.draw.circle(s,YELLOW if self.state=="SUSPICIOUS" else RED,(self.rect.centerx,self.rect.top-9),4)
        if self.health<self.max_health:
            pygame.draw.rect(s,(35,35,40),(self.rect.x,self.rect.y-8,25,4))
            pygame.draw.rect(s,RED,(self.rect.x,self.rect.y-8,25*self.health/self.max_health,4))

def make_levels():
    # 10 handcrafted, clearly different maps.  Every level has its own
    # layout, spawn, EXIT, gem positions and robot patrol routes.
    maps = [
        {
            "name":"Training Ground", "difficulty":1, "player_spawn":[70,70], "destination":[1015,650],
            "walls":[(150,130,250,35),(150,130,35,220),(470,130,35,240),(650,100,35,270),(780,360,220,35),(250,520,500,35)],
            "gems":[(90,110),(440,80),(600,90),(900,120),(110,450),(500,430),(820,290),(930,590)],
            "enemy_spawns":[(300,220),(560,180),(820,220)],
        },
        {
            "name":"Warehouse", "difficulty":1, "player_spawn":[70,650], "destination":[1015,70],
            "walls":[(110,110,180,35),(110,110,35,210),(110,285,260,35),(350,110,35,210),(450,110,35,310),(450,410,260,35),(675,110,35,335),(790,180,200,35),(790,180,35,300),(790,445,200,35)],
            "gems":[(70,570),(250,80),(420,360),(560,80),(620,500),(750,560),(920,350),(1010,120)],
            "enemy_spawns":[(220,200),(540,300),(900,250),(900,550)],
        },
        {
            "name":"Night Patrol", "difficulty":2, "player_spawn":[70,350], "destination":[1030,350],
            "walls":[(130,80,35,190),(130,450,35,190),(250,180,35,360),(370,80,35,190),(370,450,35,190),(490,180,35,360),(610,80,35,190),(610,450,35,190),(730,180,35,360),(850,80,35,190),(850,450,35,190)],
            "gems":[(80,100),(80,600),(220,100),(220,600),(460,100),(460,600),(700,100),(700,600)],
            "enemy_spawns":[(200,350),(440,350),(680,350),(920,350),(560,650)],
        },
        {
            "name":"Crossroads", "difficulty":2, "player_spawn":[70,70], "destination":[1030,650],
            "walls":[(250,20,35,250),(250,380,35,320),(500,20,35,180),(500,300,35,220),(500,600,35,120),(750,20,35,320),(750,450,35,270),(100,250,260,35),(420,250,220,35),(800,250,200,35),(100,480,220,35),(380,480,260,35),(800,480,200,35)],
            "gems":[(100,120),(350,120),(600,100),(900,120),(150,350),(650,350),(950,350),(650,600)],
            "enemy_spawns":[(180,180),(430,180),(650,400),(900,400),(900,600)],
        },
        {
            "name":"Commander Hunt", "difficulty":2, "player_spawn":[1030,650], "destination":[70,70],
            "walls":[(120,90,660,35),(90,500,660,35),(90,120,35,380),(800,120,35,380),(300,155,35,210),(270,300,35,210),(565,155,35,210),(500,300,35,210),(745,155,35,210),(700,300,35,210)],
            "gems":[(80,650),(210,80),(430,80),(670,80),(930,80),(210,650),(430,650),(700,650)],
            "enemy_spawns":[(220,220),(430,280),(650,220),(820,450),(520,480),(800,300)],
        },
        {
            "name":"Blackout", "difficulty":3, "player_spawn":[70,650], "destination":[1030,70],
            "walls":[(120,100,320,35),(520,100,460,35),(120,250,180,35),(360,250,380,35),(780,250,200,35),(120,400,300,35),(480,400,180,35),(720,400,260,35),(120,550,460,35),(640,550,340,35),(120,100,35,120),(300,250,35,120),(480,100,35,150),(720,250,35,150),(880,100,35,150)],
            "gems":[(250,180),(500,180),(760,180),(300,180),(250,350),(500,350),(760,350)],
            "enemy_spawns":[(220,180),(570,180),(900,180),(220,480),(520,480),(850,480),(600,650)],
        },
        {
            "name":"Security Sector", "difficulty":3, "player_spawn":[70,70], "destination":[1030,650],
            "walls":[(170,80,35,220),(170,420,35,220),(350,80,35,130),(350,290,35,340),(530,160,35,400),(710,80,35,220),(710,420,35,220),(890,80,35,340),(290,210,180,35),(600,210,180,35),(290,480,180,35),(600,480,180,35)],
            "gems":[(80,350),(260,110),(470,110),(620,110),(820,110),(260,620),(470,620),(820,620)],
            "enemy_spawns":[(270,170),(450,330),(630,330),(820,330),(950,550),(520,650),(250,500)],
        },
        {
            "name":"Moving Fortress", "difficulty":3, "player_spawn":[70,350], "destination":[1030,350],
            "walls":[(120,80,180,35),(360,80,180,35),(600,80,180,35),(840,80,140,35),(120,605,180,35),(360,605,180,35),(600,605,180,35),(840,605,140,35),(120,115,35,490),(300,115,35,210),(300,395,35,210),(540,115,35,210),(540,395,35,210),(780,115,35,210),(780,395,35,210),(980,115,35,490)],
            "gems":[(80,100),(230,350),(430,180),(650,180),(880,180),(430,540),(650,540),(880,540)],
            "enemy_spawns":[(220,180),(430,350),(650,350),(880,350),(950,500),(500,620),(700,100),(900,620)],
        },
        {
            "name":"Boss District", "difficulty":4, "player_spawn":[70,650], "destination":[1030,70],
            "walls":[(100,100,220,35),(380,100,340,35),(780,100,220,35),(100,585,220,35),(380,585,340,35),(780,585,220,35),(100,100,35,520),(1000,100,35,520),(300,135,35,180),(300,405,35,180),(720,135,35,180),(720,405,35,180),(480,200,35,180),(585,340,35,180),(400,340,180,35)],
            "gems":[(70,560),(200,200),(420,150),(650,150),(900,200),(200,500),(450,500),(900,500)],
            "enemy_spawns":[(220,180),(450,180),(850,180),(220,450),(800,450),(520,300),(680,500),(900,350),(560,620)],
        },
        {
            "name":"Final Contract", "difficulty":4, "player_spawn":[70,70], "destination":[1030,650],
            "walls":[(120,120,180,35),(360,120,180,35),(600,120,180,35),(840,120,140,35),(120,565,180,35),(360,565,180,35),(600,565,180,35),(840,565,140,35),(120,120,35,480),(980,120,35,480),(300,155,35,180),(300,385,35,180),(540,155,35,180),(540,385,35,180),(780,155,35,180),(780,385,35,180),(420,280,360,35),(420,405,360,35)],
            "gems":[(70,110),(210,350),(450,180),(700,180),(930,110),(210,520),(450,520),(900,520)],
            "enemy_spawns":[(220,200),(430,200),(680,200),(880,200),(220,450),(430,470),(680,470),(880,450),(550,350),(950,350)],
        },
    ]

    main_objectives = [
        "Eliminate all hostiles, collect every coin and escape.",
        "Clear the warehouse, collect every coin and escape.",
        "Cross the night patrol route, collect every coin and escape.",
        "Clear the crossroads, collect every coin and escape.",
        "Assassinate the Commander, collect every coin and escape.",
        "Survive the blackout sector, collect every coin and escape.",
        "Clear the security sector, collect every coin and escape.",
        "Infiltrate the fortress, collect every coin and escape.",
        "Defeat the Boss, collect every coin and escape.",
        "Eliminate the final target, collect every coin and escape unseen.",
    ]

    levels=[]
    for i,m in enumerate(maps):
        enemies=[]
        for n,p in enumerate(m["enemy_spawns"]):
            k="guard"
            if i>=3 and n==len(m["enemy_spawns"])-1: k="elite"
            if i>=6 and n%4==3: k="elite"
            if i==8 and n==len(m["enemy_spawns"])-1: k="boss"
            if i==9 and n in (0,len(m["enemy_spawns"])-1): k="boss" if n==len(m["enemy_spawns"])-1 else "elite"
            # Patrol points stay inside the playable area and use the level's own layout.
            offsets=[(120,0),(0,120),(-120,0),(0,-120)]
            wp=[p]
            for ox,oy in offsets[:3]:
                wp.append([clamp(p[0]+ox,50,1050),clamp(p[1]+oy,50,670)])
            enemies.append({"type":k,"waypoints":wp})
        levels.append({
            "name":m["name"], "difficulty":m["difficulty"],
            "player_spawn":m["player_spawn"], "destination":m["destination"],
            "walls":m["walls"], "enemies":enemies, "gems":m["gems"],
            "main_objective":main_objectives[i], "gem_goal":min(3+i//3,5),
            "time_limit":120-i*4, "map_version":2
        })
    return levels

def load_levels():
    os.makedirs(LEVEL_DIR,exist_ok=True)
    path=os.path.join(LEVEL_DIR,"levels.json")
    try:
        if os.path.exists(path):
            with open(path,encoding="utf8") as f:
                saved=json.load(f)
            # Replace older generated maps so every level gets the new unique layout.
            if isinstance(saved,list) and len(saved)==10 and all(x.get("map_version")==2 for x in saved):
                return saved
    except Exception:
        pass
    levels=make_levels()
    try:
        with open(path,"w",encoding="utf8") as f:json.dump(levels,f,indent=2)
    except Exception:
        pass
    return levels

def default_save():
    return {"unlocked_levels":1,"coins":0,"xp":0,"player_level":1,
            "best_score":0,"level_scores":[0]*10,"settings":{"sound":True,"difficulty":"NORMAL"},
            "upgrades":{"health":0,"speed":0,"stealth":0,"attack":0,"stamina":0},
            "skins":{"default":True},"equipped_skin":"default","skin_save_version":1}

def load_save():
    data = default_save()

    # Older versions stored save.json in the current working directory. Check
    # that location as well as the stable script folder so purchased skins are
    # not lost when launching from VS Code, a shortcut, or another terminal.
    save_paths = []
    legacy_path = os.path.abspath(os.path.join(os.getcwd(), "save.json"))
    canonical_path = os.path.abspath(SAVE_FILE)
    if legacy_path != canonical_path:
        save_paths.append(legacy_path)
    save_paths.append(canonical_path)

    loaded_any = False
    skin_version_found = False
    saved_skins = {key: False for key in SKINS}
    saved_skins["default"] = True
    saved_equipped = "default"

    for path in save_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                continue
            loaded_any = True
            for k, v in loaded.items():
                if k == "skin_save_version":
                    skin_version_found = True
                    data["skin_save_version"] = v
                elif k in ("settings", "upgrades") and isinstance(v, dict):
                    data[k].update(v)
                elif k == "level_scores" and isinstance(v, list):
                    data[k] = (v + [0] * 10)[:10]
                elif k == "skins" and isinstance(v, dict):
                    # Ownership is cumulative: a skin owned in either save file
                    # remains owned after migration to the canonical save file.
                    for skin_key in SKINS:
                        saved_skins[skin_key] = saved_skins[skin_key] or bool(v.get(skin_key, False))
                elif k == "equipped_skin" and v in SKINS:
                    saved_equipped = v
                elif k in data:
                    data[k] = v
        except (OSError, ValueError, TypeError):
            # A missing/corrupt legacy save must not prevent the game starting.
            continue

    # One-time reset for older save files: start with only CYBER unlocked.
    # Once this version marker is saved, later purchases remain unlocked.
    if not skin_version_found:
        saved_skins = {key: (key == "default") for key in SKINS}
        saved_equipped = "default"
    data["skins"] = saved_skins
    data["skins"]["default"] = True
    data["skin_save_version"] = 1
    try:
        data["coins"] = max(0, int(data.get("coins", 0)))
    except (ValueError, TypeError):
        data["coins"] = 0

    # Each launch starts at Level 1, but purchased skins remain persistent.
    data["unlocked_levels"] = 1
    if saved_equipped not in SKINS or not data["skins"].get(saved_equipped, False):
        data["equipped_skin"] = "default"
    else:
        data["equipped_skin"] = saved_equipped

    # Write migrated ownership to the stable location immediately, so future
    # launches use the same save regardless of their working directory.
    if loaded_any:
        save_game(data)
    return data

def save_game(data):
    tmp=SAVE_FILE+".tmp"
    try:
        data["coins"]=max(0,int(data.get("coins",0)))
        with open(tmp,"w",encoding="utf8") as f:
            json.dump(data,f,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,SAVE_FILE)
    except (OSError,ValueError,TypeError):
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except OSError: pass

class Game:
    def __init__(self):
        pygame.init()
        try:pygame.mixer.init()
        except pygame.error:pass
        self.screen=pygame.display.set_mode((WIDTH,HEIGHT))
        pygame.display.set_caption("- Stealth Campaign -")
        self.clock=pygame.time.Clock()
        self.font=pygame.font.SysFont("arial",26,bold=True)
        self.big=pygame.font.SysFont("arial",54,bold=True)
        self.small=pygame.font.SysFont("arial",18)
        self.levels=load_levels();self.save=load_save()
        self.sound=SoundManager(self.save["settings"]["sound"])
        self.state="menu";self.level=1;self.score=0;self.kills=0
        self.particles=[];self.noise=[];self.messages=[];self.shake=0
        self.start_time=time.time();self.last_step=0
    def text(self,s,pos,font=None,color=WHITE,center=False):
        surf=(font or self.small).render(str(s),True,color)
        p=(pos[0]-surf.get_width()/2,pos[1]-surf.get_height()/2) if center else pos
        self.screen.blit(surf,p)
    def button(self,rect,label,enabled=True):
        pygame.draw.rect(self.screen,(40,47,62) if enabled else (25,28,35),rect,border_radius=8)
        pygame.draw.rect(self.screen,PLAYER if enabled else MUTED,rect,2,border_radius=8)
        self.text(label,rect.center,self.font,WHITE if enabled else MUTED,True)
    def start_level(self,n):
        self.level=clamp(n,1,10);cfg=self.levels[self.level-1]
        walls=[Wall(0,0,WIDTH,20),Wall(0,0,20,HEIGHT),Wall(WIDTH-20,0,20,HEIGHT),Wall(0,HEIGHT-20,WIDTH,20)]
        walls += [Wall(*x) for x in cfg["walls"]]
        self.walls=walls;self.pathfinder=Pathfinder(walls)
        self.player=Player(cfg["player_spawn"])
        self.player.skin=self.save.get("equipped_skin","default")
        u=self.save["upgrades"]
        self.player.max_health+=u.get("health",0)*10;self.player.health=self.player.max_health
        self.player.max_stamina+=u.get("stamina",0)*10;self.player.stamina=self.player.max_stamina
        self.enemies=[Enemy(e["type"],e["waypoints"]) for e in cfg["enemies"]]
        self.gems=[Gem(*g) for g in cfg["gems"]]
        self.destination=pygame.Rect(0,0,55,55);self.destination.center=cfg["destination"]
        self.score=0;self.kills=0;self.pending_coins=0
        self.particles=[];self.noise=[];self.messages=[]
        self.start_time=time.time();self.state="playing"
    def add_message(self,msg,color=WHITE):
        self.messages.insert(0,[msg,color,120]);self.messages=self.messages[:4]
    def emit_noise(self,pos,radius):
        self.noise.append((pos,radius))
    def attack(self):
        target=self.player.attack(self.enemies,self.particles)
        self.emit_noise(self.player.center(),230)
        if target:
            self.kills+=1;self.score+=150
            self.sound.play("kill")
            self.add_message("ASSASSINATION +150",GREEN)
            if target.kind=="boss":self.score+=300;self.add_message("BOSS ELIMINATED +300",YELLOW)
        else:self.add_message("MISSED",MUTED)
    def update(self):
        if self.state!="playing":return
        dt=time.time()-self.start_time
        keys=pygame.key.get_pressed()
        self.player.crouching=keys[pygame.K_c]
        self.player.sprinting=(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and not self.player.crouching and self.player.stamina>1
        speed=2.8+self.save["upgrades"].get("speed",0)*.13
        if self.player.crouching:speed*=.52
        if self.player.sprinting:speed*=1.65;self.player.stamina=max(0,self.player.stamina-.9)
        dx=(keys[pygame.K_d] or keys[pygame.K_RIGHT])-(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=(keys[pygame.K_s] or keys[pygame.K_DOWN])-(keys[pygame.K_w] or keys[pygame.K_UP])
        if dx or dy:
            self.player.move(dx*speed,dy*speed,self.walls)
            noise=25 if self.player.crouching else (85 if self.player.sprinting else 50)
            self.emit_noise(self.player.center(),noise)
        self.player.update()
        if self.player.dash_timer:
            self.player.move(math.cos(self.player.angle)*9,math.sin(self.player.angle)*9,self.walls)
        self.noise=self.noise[-15:]
        for e in self.enemies:
            was_visible=e.was_visible
            e.update(self.player,self.walls,self.pathfinder,self.noise,self.particles)
            visible_now=e.sees(self.player,self.walls)
            if visible_now and not was_visible:self.sound.play("detect")
            e.was_visible=visible_now
        for g in self.gems:
            if not g.collected and self.player.rect.colliderect(g.rect):
                # Gems are collected during the mission, but their coins are
                # kept pending until the player reaches the exit successfully.
                g.collected=True
                self.score+=75
                self.pending_coins += 10
                self.sound.play("coin")
                self.add_message("GEM +75  •  +10 COINS AT EXIT",BLUE)
                self.emit_noise(self.player.center(),35)
        self.particles=[p for p in self.particles if p.life>0]
        for p in self.particles:p.update()
        # The EXIT only completes the mission after BOTH objectives are finished:
        # 1) every gem/coin has been collected, and
        # 2) every robot has been eliminated.
        all_coins_collected = all(g.collected for g in self.gems)
        all_robots_killed = all(e.dead for e in self.enemies)
        if self.player.alive and self.player.rect.colliderect(self.destination):
            if all_coins_collected and all_robots_killed:
                self.complete_level(dt)
            elif not all_coins_collected:
                remaining=sum(not g.collected for g in self.gems)
                self.add_message(f"EXIT LOCKED • COLLECT ALL COINS ({remaining} LEFT)",YELLOW)
            elif not all_robots_killed:
                remaining=sum(not e.dead for e in self.enemies)
                self.add_message(f"EXIT LOCKED • ELIMINATE ALL ROBOTS ({remaining} LEFT)",RED)
        elif not self.player.alive:
            self.state="gameover"
        elif dt>self.levels[self.level-1]["time_limit"]:
            self.add_message("TIME LIMIT FAILED",RED);self.state="gameover"
        self.shake=max(0,self.shake-1)
    def complete_level(self,elapsed):
        cfg=self.levels[self.level-1];collected=sum(g.collected for g in self.gems)
        stars=1
        if collected>=cfg["gem_goal"]:stars+=1
        if elapsed<=cfg["time_limit"]*.65:stars+=1
        self.score+=250+stars*100
        self.save["level_scores"][self.level-1]=max(self.save["level_scores"][self.level-1],self.score)
        self.save["best_score"]=max(self.save["best_score"],self.score)

        # BANK ALL GEM COINS ONLY AFTER SUCCESSFULLY REACHING THE EXIT.
        # Level completion coins are also awarded here.
        gem_coins=self.pending_coins
        completion_coins=50+stars*25
        total_coins=gem_coins+completion_coins
        self.save["coins"]=max(0,int(self.save.get("coins",0)))+total_coins
        self.save["xp"]+=100+stars*50

        if gem_coins:
            self.add_message(f"EXIT REWARD +{gem_coins} GEM COINS",BLUE)
        self.add_message(f"MISSION REWARD +{completion_coins} COINS",YELLOW)

        self.pending_coins=0
        if self.level<10:self.save["unlocked_levels"]=max(self.save["unlocked_levels"],self.level+1)
        save_game(self.save);self.stars=stars;self.sound.play("complete");self.state="win"
    def draw_world(self):
        s=self.screen;s.fill(BG)
        for x in range(0,WIDTH,CELL):pygame.draw.line(s,GRID,(x,0),(x,HEIGHT))
        for y in range(0,HEIGHT,CELL):pygame.draw.line(s,GRID,(0,y),(WIDTH,y))
        pulse=5+int(4*math.sin(pygame.time.get_ticks()*.006))
        all_coins_collected = all(g.collected for g in self.gems)
        all_robots_killed = all(e.dead for e in self.enemies)
        exit_ready = all_coins_collected and all_robots_killed
        exit_color = (30,130,80) if exit_ready else (120,90,35)
        pygame.draw.rect(s,exit_color,self.destination,border_radius=10)
        pygame.draw.rect(s,PLAYER,self.destination.inflate(pulse,pulse),3,border_radius=12)
        self.text("EXIT" if exit_ready else "LOCKED",self.destination.center,self.small,WHITE,True)
        for g in self.gems:g.draw(s,pygame.time.get_ticks())
        for w in self.walls:w.draw(s)
        for e in self.enemies:e.draw_vision(s,self.walls)
        for e in self.enemies:e.draw(s)
        self.player.draw(s)
        for p in self.particles:p.draw(s)
    def draw_hud(self):
        pygame.draw.rect(self.screen,(12,14,20),(0,0,WIDTH,70))
        # health
        self.text(f"HP {int(self.player.health)}/{int(self.player.max_health)}",(18,10),self.small)
        pygame.draw.rect(self.screen,(45,45,50),(18,34,170,10));pygame.draw.rect(self.screen,RED,(18,34,170*self.player.health/self.player.max_health,10))
        self.text(f"STAMINA",(210,10),self.small)
        pygame.draw.rect(self.screen,(45,45,50),(210,34,140,10));pygame.draw.rect(self.screen,BLUE,(210,34,140*self.player.stamina/self.player.max_stamina,10))
        self.text(f"LEVEL {self.level}/10",(380,10),self.font)
        self.text(f"SCORE {self.score}",(570,10),self.font,YELLOW)
        self.text(f"COINS {self.save['coins']}",(760,10),self.font,BLUE)
        if getattr(self,"pending_coins",0)>0:
            self.text(f"+{self.pending_coins} PENDING",(760,39),self.small,YELLOW)
        cfg=self.levels[self.level-1]
        elapsed=int(time.time()-self.start_time);remaining=max(0,cfg["time_limit"]-elapsed)
        self.text(f"TIME {remaining}s",(925,10),self.font,RED if remaining<20 else WHITE)
        if self.enemies:
            remaining_robots=sum(not e.dead for e in self.enemies)
            self.text(f"ROBOTS {remaining_robots}",(18,52),self.small,GREEN if remaining_robots==0 else WHITE)
        remaining_coins=sum(not g.collected for g in self.gems)
        self.text(f"COINS LEFT {remaining_coins}",(18,66),self.small,GREEN if remaining_coins==0 else YELLOW)
        detected=max([e.alert for e in self.enemies] or [0])
        self.text("DETECTION",(210,52),self.small)
        pygame.draw.rect(self.screen,(45,45,50),(305,55,170,8))
        pygame.draw.rect(self.screen,RED,(305,55,170*detected/100,8))
        cfg=self.levels[self.level-1]
        self.text(cfg["main_objective"],(500,53),self.small,MUTED)
    def draw_overlay(self):
        ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA);ov.fill((0,0,0,175));self.screen.blit(ov,(0,0))
    def draw(self):
        if self.state in ("playing","paused","win","gameover"):self.draw_world();self.draw_hud()
        else:self.screen.fill(BG)
        if self.state=="menu":self.draw_menu()
        elif self.state=="levels":self.draw_levels()
        elif self.state=="shop":self.draw_shop()
        elif self.state=="skins":self.draw_skins()
        elif self.state=="settings":self.draw_settings()
        elif self.state=="paused":self.draw_pause()
        elif self.state=="win":self.draw_win()
        elif self.state=="gameover":self.draw_gameover()
        pygame.display.flip()
    def draw_menu(self):
        self.text("Stealth Campaign",(WIDTH//2,95),self.big,PLAYER,True)
        self.text("STEALTH ACTION CAMPAIGN",(WIDTH//2,145),self.font,MUTED,True)
        self.text(f"Best Score: {self.save['best_score']}   •   Player Level: {self.save['player_level']}",(WIDTH//2,185),self.small,WHITE,True)
        for i,(lab,st) in enumerate([("PLAY","levels"),("UPGRADES","shop"),("SKINS","skins"),("SETTINGS","settings")]):
            self.button(pygame.Rect(WIDTH//2-150,220+i*62,300,48),lab)
        equipped_name=SKINS.get(self.save.get("equipped_skin","default"),SKINS["default"])["name"]
        self.text(f"CURRENT SKIN: {equipped_name}",(WIDTH//2,490),self.small,WHITE,True)
        self.text("WASD Move  •  SHIFT Sprint  •  C Crouch  •  F/Mouse Attack  •  SPACE Dash",(WIDTH//2,520),self.small,MUTED,True)
        self.text("10 missions • stealth AI • targets • upgrades • persistent saves",(WIDTH//2,505),self.small,MUTED,True)
    def draw_levels(self):
        self.text("SELECT MISSION",(WIDTH//2,55),self.big,PLAYER,True)
        for i,cfg in enumerate(self.levels):
            col=i%2;row=i//2
            r=pygame.Rect(90+col*480,105+row*105,440,85)
            unlocked=i+1<=self.save["unlocked_levels"]
            self.button(r,f"{i+1:02d}  {cfg['name']}"+("" if unlocked else "  [LOCKED]"),unlocked)
            self.text(f"Difficulty {cfg['difficulty']}  •  Best {self.save['level_scores'][i]}",(r.x+15,r.bottom-22),self.small,MUTED if unlocked else (90,90,95))
        self.button(pygame.Rect(430,665,240,42),"BACK")
    def draw_shop(self):
        self.text("STEALTH UPGRADES",(WIDTH//2,70),self.big,PLAYER,True)
        u=self.save["upgrades"]
        items=[("health","Health +10",100),("speed","Speed +0.18",100),("stealth","Stealth",125),("attack","Attack",125),("stamina","Stamina +10",100)]
        for i,(key,label,cost) in enumerate(items):
            y=155+i*75;r=pygame.Rect(220,y,660,58)
            self.button(r,f"{label}   LEVEL {u[key]}   •   {cost} COINS")
        self.text(f"COINS: {self.save['coins']}",(WIDTH//2,570),self.font,YELLOW,True)
        self.button(pygame.Rect(430,630,240,45),"BACK")
    def draw_skins(self):
        self.text("ROBOT SKINS",(WIDTH//2,55),self.big,PLAYER,True)
        self.text(f"COINS: {self.save['coins']}",(WIDTH-170,35),self.font,YELLOW,True)
        equipped=self.save.get("equipped_skin","default")

        for i,(key,skin) in enumerate(SKINS.items()):
            col=i%2; row=i//2
            r=pygame.Rect(100+col*450,105+row*105,400,85)
            owned=self.save["skins"].get(key,False)
            is_equipped=(key==equipped)

            pygame.draw.rect(self.screen,(30,35,46),r,border_radius=10)
            pygame.draw.rect(self.screen,skin["color"] if owned else MUTED,r,2,border_radius=10)

            # Small live robot preview.
            cx,cy=r.x+48,r.y+42
            pygame.draw.circle(self.screen,(8,10,15),(cx,cy),18)
            pygame.draw.circle(self.screen,skin["color"] if owned else (70,72,80),(cx,cy),14)
            pygame.draw.circle(self.screen,skin["accent"] if owned else MUTED,(cx,cy),5)

            self.text(skin["name"],(r.x+80,r.y+13),self.font,WHITE)
            if is_equipped:
                status="EQUIPPED"
                status_color=GREEN
            elif owned:
                status="OWNED • CLICK TO EQUIP"
                status_color=BLUE
            else:
                status=f"{skin['cost']} COINS • CLICK TO BUY"
                status_color=YELLOW
            self.text(status,(r.x+80,r.y+47),self.small,status_color)

        self.button(pygame.Rect(430,650,240,45),"BACK")

    def draw_settings(self):
        self.text("SETTINGS",(WIDTH//2,100),self.big,PLAYER,True)
        self.button(pygame.Rect(350,220,400,55),f"SOUND: {'ON' if self.save['settings']['sound'] else 'OFF'}")
        self.button(pygame.Rect(350,295,400,55),f"DIFFICULTY: {self.save['settings']['difficulty']}")
        self.text("Click difficulty to cycle EASY → NORMAL → HARD → NIGHTMARE",(WIDTH//2,390),self.small,MUTED,True)
        self.button(pygame.Rect(430,550,240,45),"BACK")
    def draw_pause(self):
        self.draw_overlay();self.text("PAUSED",(WIDTH//2,170),self.big,PLAYER,True)
        self.button(pygame.Rect(380,250,340,55),"RESUME")
        self.button(pygame.Rect(380,320,340,55),"RESTART")
        self.button(pygame.Rect(380,390,340,55),"MAIN MENU")
    def draw_win(self):
        self.draw_overlay();self.text(f"MISSION {self.level} COMPLETE",(WIDTH//2,170),self.big,PLAYER,True)
        self.text(f"Score {self.score}   •   Stars {'★'*self.stars}",(WIDTH//2,245),self.font,YELLOW,True)
        self.text("All collected gem coins are added after reaching the EXIT.",(WIDTH//2,285),self.small,MUTED,True)
        self.button(pygame.Rect(250,390,180,55),"REPLAY")
        self.button(pygame.Rect(460,390,180,55),"NEXT" if self.level<10 else "MENU")
        self.button(pygame.Rect(670,390,180,55),"MENU")
    def draw_gameover(self):
        self.draw_overlay();self.text("MISSION FAILED",(WIDTH//2,190),self.big,RED,True)
        self.text("You were detected, defeated, or ran out of time.",(WIDTH//2,260),self.font,MUTED,True)
        self.button(pygame.Rect(330,370,200,55),"RETRY")
        self.button(pygame.Rect(570,370,200,55),"MENU")
    def handle_click(self,pos):
        x,y=pos
        if self.state!="playing": self.sound.play("click")
        if self.state=="menu":
            if pygame.Rect(WIDTH//2-150,220,300,48).collidepoint(pos):self.state="levels"
            elif pygame.Rect(WIDTH//2-150,282,300,48).collidepoint(pos):self.state="shop"
            elif pygame.Rect(WIDTH//2-150,344,300,48).collidepoint(pos):self.state="skins"
            elif pygame.Rect(WIDTH//2-150,406,300,48).collidepoint(pos):self.state="settings"
        elif self.state=="levels":
            for i in range(10):
                col=i%2;row=i//2;r=pygame.Rect(90+col*480,105+row*105,440,85)
                if r.collidepoint(pos) and i+1<=self.save["unlocked_levels"]:self.start_level(i+1);return
            if pygame.Rect(430,665,240,42).collidepoint(pos):self.state="menu"
        elif self.state=="shop":
            if pygame.Rect(430,630,240,45).collidepoint(pos):self.state="menu";return
            items=[("health",100),("speed",100),("stealth",125),("attack",125),("stamina",100)]
            for i,(key,cost) in enumerate(items):
                if pygame.Rect(220,155+i*75,660,58).collidepoint(pos) and self.save["coins"]>=cost:
                    self.save["coins"]-=cost;self.save["upgrades"][key]+=1;save_game(self.save)
        elif self.state=="skins":
            if pygame.Rect(430,650,240,45).collidepoint(pos):
                self.state="menu";return

            skin_items=list(SKINS.items())
            for i,(key,skin) in enumerate(skin_items):
                col=i%2; row=i//2
                r=pygame.Rect(100+col*450,105+row*105,400,85)
                if not r.collidepoint(pos):
                    continue

                owned=self.save["skins"].get(key,False)
                if owned:
                    self.save["equipped_skin"]=key
                    if hasattr(self,"player"):
                        self.player.skin=key
                    save_game(self.save)
                    self.add_message(f"SKIN EQUIPPED: {skin['name']}",GREEN)
                elif self.save["coins"]>=skin["cost"]:
                    self.save["coins"]-=skin["cost"]
                    self.save["skins"][key]=True
                    self.save["equipped_skin"]=key
                    if hasattr(self,"player"):
                        self.player.skin=key
                    save_game(self.save)
                    self.add_message(f"PURCHASED: {skin['name']}",GREEN)
                else:
                    self.add_message(f"NEED {skin['cost']-self.save['coins']} MORE COINS",RED)
                return
        elif self.state=="settings":
            if pygame.Rect(350,220,400,55).collidepoint(pos):
                self.save["settings"]["sound"]=not self.save["settings"]["sound"]
                self.sound.set_enabled(self.save["settings"]["sound"])
                save_game(self.save)
            elif pygame.Rect(350,295,400,55).collidepoint(pos):
                vals=["EASY","NORMAL","HARD","NIGHTMARE"];cur=self.save["settings"]["difficulty"];self.save["settings"]["difficulty"]=vals[(vals.index(cur)+1)%4];save_game(self.save)
            elif pygame.Rect(430,550,240,45).collidepoint(pos):self.state="menu"
        elif self.state=="playing":
            if y<80 and x>WIDTH-130:self.state="paused"
            else:self.attack()
        elif self.state=="paused":
            if pygame.Rect(380,250,340,55).collidepoint(pos):self.state="playing"
            elif pygame.Rect(380,320,340,55).collidepoint(pos):self.start_level(self.level)
            elif pygame.Rect(380,390,340,55).collidepoint(pos):self.state="menu"
        elif self.state=="win":
            if pygame.Rect(250,390,180,55).collidepoint(pos):self.start_level(self.level)
            elif pygame.Rect(460,390,180,55).collidepoint(pos):
                if self.level<10:self.start_level(self.level+1)
                else:self.state="menu"
            elif pygame.Rect(670,390,180,55).collidepoint(pos):self.state="menu"
        elif self.state=="gameover":
            if pygame.Rect(330,370,200,55).collidepoint(pos):self.start_level(self.level)
            elif pygame.Rect(570,370,200,55).collidepoint(pos):self.state="menu"
    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type==pygame.QUIT:
                    save_game(self.save);pygame.quit();return
                if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:self.handle_click(e.pos)
                if e.type==pygame.KEYDOWN:
                    if self.state=="playing":
                        if e.key==pygame.K_f:self.attack()
                        elif e.key==pygame.K_SPACE:self.player.dash(self.walls);self.emit_noise(self.player.center(),240)
                        elif e.key==pygame.K_ESCAPE:self.state="paused"
                        elif e.key==pygame.K_r:self.start_level(self.level)
                    elif self.state=="paused":
                        if e.key==pygame.K_ESCAPE:self.state="playing"
                        elif e.key==pygame.K_r:self.start_level(self.level)
                    elif self.state=="gameover" and e.key==pygame.K_r:self.start_level(self.level)
                    elif self.state=="win":
                        if e.key==pygame.K_r:self.start_level(self.level)
                        elif e.key==pygame.K_n and self.level<10:self.start_level(self.level+1)
                    elif e.key==pygame.K_m:self.state="menu"
            self.update();self.draw();self.clock.tick(FPS)

if __name__=="__main__":
    Game().run()
