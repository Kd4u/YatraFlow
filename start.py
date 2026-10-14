#!/usr/bin/env python3
"""YatraFlow Studio — launch with `python3 start.py`. Python standard library only."""
from __future__ import annotations
import argparse, copy, datetime as dt, json, math, random, threading, time, webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
# Transcribed from user-provided Bihar tourism reports. These are monthly visits to Bodhgaya, not temple admissions.
TOURISM={
 '2021':{'domestic':[45026,47574,46263,12418,710,2880,6779,8768,59972,47368,42614,31000],'foreign':[0,0,0,0,0,0,0,0,0,0,46,0]},
 '2025':{'domestic':[253619,243545,228677,160771,158988,111314,123622,130172,255379,144925,161534,208000],'foreign':[22356,17949,12659,2580,1910,1504,2639,5898,6773,11694,19247,66606]},
 '2026':{'domestic':[285811,272151,251157,198573,189392,133125,137145,145220,None,None,None,None],'foreign':[40320,36106,37247,7046,4171,3495,6028,12703,None,None,None,None]}
}
# A 1 km x 1 km georeferenced study square centered near Mahabodhi Temple.
# Landmark anchors use published OSM/Mapcarta coordinates; modeled graph edges are
# illustrative and NOT verified pedestrian rights-of-way or authorized gates.
MAP_BOUNDS={'north':24.6999,'south':24.6909,'west':84.9855,'east':84.9955}
def project(lat,lon):
 return (round((lon-MAP_BOUNDS['west'])/(MAP_BOUNDS['east']-MAP_BOUNDS['west'])*860,1),round((MAP_BOUNDS['north']-lat)/(MAP_BOUNDS['north']-MAP_BOUNDS['south'])*720,1))
LANDMARKS=[
 {'name':'Mahabodhi Temple','lat':24.69593,'lon':84.99139,'kind':'heritage','source':'OSM way 314531108'},
 {'name':'Archaeological Museum','lat':24.69484,'lon':84.98746,'kind':'museum','source':'OSM way 312572546'},
 {'name':'Muchalinda Sarovar','lat':24.69469,'lon':84.99139,'kind':'water','source':'OSM way 274190414'},
 {'name':'Mahabodhi Temple Complex','lat':24.69538,'lon':84.99151,'kind':'heritage','source':'OSM way 120392586'}]
NODES={
 'west':project(24.6963,84.9859),'north':project(24.6991,84.9905),
 'south':project(24.6916,84.9893),'east':project(24.6962,84.9949),
 'market':project(24.6963,84.9882),'plaza':project(24.69565,84.9897),
 'temple':project(24.69593,84.99139),'garden':project(24.69495,84.9927),
 'monastery':project(24.6977,84.9937),'museum':project(24.69484,84.98746),
 'pond':project(24.69469,84.99139)
}
EDGES=[('west','market'),('market','plaza'),('market','museum'),('museum','south'),('north','temple'),('temple','plaza'),('plaza','garden'),('garden','east'),('garden','pond'),('pond','south'),('temple','monastery'),('monastery','east'),('plaza','pond'),('market','temple'),('plaza','monastery')]
ZONES=[('Market Approach','market',310),('Central Plaza','plaza',370),('Temple Approach','temple',290),('Garden Walk','garden',280),('Monastery Route','monastery',220),('Museum Lane','museum',200),('South Promenade','pond',230)]
GATES=['west','north','south','east']
ATTRACTIONS=['temple','monastery','museum','garden','pond','market']
WEATHER=json.loads((ROOT/'data/weather_hourly.json').read_text())
WEATHER_BY_MONTH={}
for row in WEATHER['records']:
 key=row[0][:7]; WEATHER_BY_MONTH.setdefault(key,[]).append(row)

class Engine:
 def __init__(self):
  self.lock=threading.RLock();self.rng=random.Random(2026)
  self.config={'target_crowd':650,'speed':4,'arrival_multiplier':1.0,'festival':False,'rain_override':False,'diversion':False,'gate_control':False,'walking_speed':1.15,'dwell_minutes':22,'site_share':0.24,'month':12,'year':2025,'hour':11,'red_threshold':90,'amber_threshold':70,'seed':2026,'paused':False}
  self.clock=0.;self.agents=[];self.next_id=1;self.history=deque(maxlen=200);self.events=deque(maxlen=80);self.alerts={};self.completed=0;self.arrivals=0;self.diverted=0;self.previous_zone={};self.last_history=0;self.reset()
 def reset(self):
  with self.lock:
   self.rng=random.Random(int(self.config['seed']));self.clock=0.;self.agents=[];self.next_id=1;self.history.clear();self.events.clear();self.alerts={};self.completed=0;self.arrivals=0;self.diverted=0;self.last_history=0
   for _ in range(int(self.config['target_crowd'])):self.spawn(initial=True)
   self.events.appendleft({'at':0,'type':'system','message':'Simulation initialized · seeded and reproducible'})
 def weather(self):
  key=f"{self.config['year']}-{self.config['month']:02d}";arr=WEATHER_BY_MONTH.get(key,[])
  if not arr:return {'temp':27,'rain':0,'humidity':60,'source':'fallback estimate'}
  matching=[r for r in arr if int(r[0][11:13])==self.config['hour']]
  if not matching:matching=arr
  return {'temp':round(sum(r[1] for r in matching)/len(matching),1),'rain':round(sum(r[2] for r in matching)/len(matching),2),'humidity':round(sum(r[3] for r in matching)/len(matching)),'source':'uploaded Open-Meteo historical observations (hourly means)'}
 def monthly(self):
  y=str(self.config['year']);m=self.config['month']-1;d=TOURISM[y]['domestic'][m];f=TOURISM[y]['foreign'][m]
  return None if d is None else d+f
 def demand(self):
  monthly=self.monthly();days=31 if self.config['month'] in (1,3,5,7,8,10,12) else 30 if self.config['month']!=2 else 28
  hourly_weight=([.025,.018,.012,.01,.01,.014,.025,.045,.075,.095,.105,.11,.10,.085,.075,.07,.055,.045,.035,.028,.022,.016,.012,.01][self.config['hour']])
  # hourly weights are normalized to sum to 1. Baseline arrivals are estimated, not directly measured.
  weights=[.025,.018,.012,.01,.01,.014,.025,.045,.075,.095,.105,.11,.10,.085,.075,.07,.055,.045,.035,.028,.022,.016,.012,.01]
  share=max(.01,min(.99,self.config['site_share']))
  base=(monthly/days*share*hourly_weight/sum(weights)) if monthly is not None else 0
  w=self.weather();rain_factor=.78 if self.config['rain_override'] else (.88 if w['rain']>2 else 1)
  factor=self.config['arrival_multiplier']*(1.85 if self.config['festival'] else 1)*rain_factor
  return {'hourly_site_arrivals_estimate':round(base*factor),'monthly_city_visits':monthly,'weather':w,'rain_factor':rain_factor,'festival_factor':1.85 if self.config['festival'] else 1,'assumed_site_share':share}
 def shortest(self,a,b,blocked=None):
  import heapq
  graph={n:[] for n in NODES}
  for x,y in EDGES:
   dist=math.dist(NODES[x],NODES[y]);penalty=2.2 if self.config['diversion'] and ('plaza' in (x,y) or 'temple' in (x,y)) else 1
   if self.config['gate_control'] and ('north' in (x,y)):penalty*=5
   graph[x].append((y,dist*penalty));graph[y].append((x,dist*penalty))
  heap=[(0,a,[])];seen=set()
  while heap:
   cost,node,path=heapq.heappop(heap)
   if node in seen:continue
   if node==b:return path+[node]
   seen.add(node)
   for n,d in graph[node]:heapq.heappush(heap,(cost+d,n,path+[node]))
  return [a,b]
 def spawn(self,initial=False):
  gate=self.rng.choice(GATES);dest=self.rng.choices(ATTRACTIONS,weights=[40,16,11,14,9,10])[0]
  route=self.shortest(gate,dest);pos=NODES[gate];speed=self.config['walking_speed']*self.rng.uniform(.78,1.22)
  a={'id':self.next_id,'x':pos[0],'y':pos[1],'route':route,'index':1,'dest':dest,'speed':speed,'dwell':self.rng.uniform(.6,1.4)*self.config['dwell_minutes']*60,'phase':'walking','age':0}
  self.next_id+=1
  if initial:
   # Distribute existing agents across a plausible path/dwell phase to avoid all dots at entrances.
   if self.rng.random()<.38:
    a['x'],a['y']=NODES[dest];a['index']=len(route);a['phase']='dwell';a['dwell']*=self.rng.random()
   else:
    seg=self.rng.randrange(max(1,len(route)-1));u=self.rng.random();p=NODES[route[seg]];q=NODES[route[min(seg+1,len(route)-1)]];a['x']=p[0]+(q[0]-p[0])*u;a['y']=p[1]+(q[1]-p[1])*u;a['index']=min(seg+1,len(route)-1)
  self.agents.append(a);self.arrivals+=1
 def zone_counts(self):
  counts={z[0]:0 for z in ZONES}
  for a in self.agents:
   closest=min(ZONES,key=lambda z:(a['x']-NODES[z[1]][0])**2+(a['y']-NODES[z[1]][1])**2)
   counts[closest[0]]+=1
  return counts
 def step(self,real_dt):
  with self.lock:
   if self.config['paused']:return
   secs=min(real_dt,1.5)*self.config['speed'];self.clock+=secs
   target=max(20,min(2600,round(self.config['target_crowd']*self.config['arrival_multiplier']*(1.45 if self.config['festival'] else 1)*(.78 if self.config['rain_override'] else 1))));delta=target-len(self.agents)
   if delta>0:
    for _ in range(min(delta,max(1,int(15*real_dt)))):self.spawn()
   # Target is a desired steady population; removal happens through controlled exits rather than deleting agents.
   grid={}
   for b in self.agents:
    cell=(int(b['x']//32),int(b['y']//32));grid[cell]=grid.get(cell,0)+1
   for a in self.agents:
    a['age']+=secs
    if a['phase']=='dwell':
     a['dwell']-=secs
     if a['dwell']<=0:
      end=self.rng.choice(GATES);a['route']=self.shortest(a['dest'],end);a['index']=1;a['phase']='exit'
     continue
    if a['index']>=len(a['route']):
     if a['phase']=='exit':a['phase']='done'
     else:a['phase']='dwell'
     continue
    p=NODES[a['route'][a['index']]];dx=p[0]-a['x'];dy=p[1]-a['y'];dist=math.hypot(dx,dy)
    # Local slowdown is a behavioral assumption, not a calibrated pedestrian fundamental diagram.
    cx,cy=int(a['x']//32),int(a['y']//32);near=sum(grid.get((cx+dx,cy+dy),0) for dx in (-1,0,1) for dy in (-1,0,1))
    slow=max(.24,1-.025*max(0,near-8));travel=a['speed']*secs*7*slow
    if dist<=travel:
     a['x'],a['y']=p;a['index']+=1
    else:a['x']+=dx/dist*travel;a['y']+=dy/dist*travel
   before=len(self.agents);self.agents=[a for a in self.agents if a['phase']!='done'];self.completed+=before-len(self.agents)
   if len(self.agents)>target:
    # Exit at a bounded rate by marking agents to leave; never teleport them away.
    excess=min(len(self.agents)-target,max(1,int(8*real_dt)))
    candidates=[a for a in self.agents if a['phase']=='dwell']
    for a in candidates[:excess]:a['dwell']=0
   if self.clock-self.last_history>=15:
    self.last_history=self.clock;self.record()
 def record(self):
  counts=self.zone_counts();zones=[]
  for name,node,capacity in ZONES:
   count=counts[name];pct=100*count/capacity;severity='critical' if pct>=self.config['red_threshold'] else 'warning' if pct>=self.config['amber_threshold'] else 'normal'
   zones.append({'name':name,'node':node,'count':count,'capacity':capacity,'occupancy':round(pct,1),'severity':severity})
   if severity!='normal' and name not in self.alerts:
    self.alerts[name]={'id':name,'zone':name,'severity':severity,'status':'open','created_at':round(self.clock),'ack_at':None,'resolved_at':None,'note':''}
    self.events.appendleft({'at':round(self.clock),'type':'alert','message':f'{name}: {severity.upper()} threshold reached'})
   elif name in self.alerts and self.alerts[name]['status']=='resolved' and severity=='normal':pass
   elif name in self.alerts and severity!='normal' and self.alerts[name]['status']=='resolved':
    self.alerts[name]['status']='open';self.alerts[name]['created_at']=round(self.clock)
   if name in self.alerts:self.alerts[name]['severity']=severity
  self.history.append({'t':round(self.clock),'total':len(self.agents),'zones':{z['name']:z['count'] for z in zones}})
 def forecast(self):
  # Explicitly identified as a simple model, not trained ML.
  if not self.history:return []
  h=list(self.history);current=h[-1]['total'];window=h[-min(8,len(h)):]
  rate=(window[-1]['total']-window[0]['total'])/max(1,window[-1]['t']-window[0]['t'])
  # Damp recent trend toward configured equilibrium; avoid unbounded linear extrapolation.
  out=[]
  for mins in (15,30,60):
   t=mins*60;target=self.config['target_crowd'];estimate=target+(current-target)*math.exp(-t/900)+rate*min(t,300)*math.exp(-t/600)
   out.append({'minutes':mins,'visitors':max(0,round(estimate)),'method':'damped trend + configured target (heuristic)'})
  return out
 def snapshot(self,include_agents=True):
  with self.lock:
   if not self.history or self.clock-self.last_history>=15:self.record();self.last_history=self.clock
   counts=self.zone_counts();zones=[]
   for name,node,cap in ZONES:
    n=counts[name];pct=100*n/cap
    zones.append({'name':name,'node':node,'count':n,'capacity':cap,'occupancy':round(pct,1),'severity':'critical' if pct>=self.config['red_threshold'] else 'warning' if pct>=self.config['amber_threshold'] else 'normal'})
   result={'clock':round(self.clock,1),'config':dict(self.config),'total':len(self.agents),'arrivals':self.arrivals,'exits':self.completed,'zones':zones,'demand':self.demand(),'forecast':self.forecast(),'alerts':list(self.alerts.values()),'events':list(self.events)[:25],'history':list(self.history)[-80:],'nodes':NODES,'edges':EDGES,'map_bounds':MAP_BOUNDS,'landmarks':LANDMARKS,'tourism':TOURISM,'months':MONTHS,'data_quality':{'tourism':'Observed monthly city-wide visitor statistics','weather':'Observed/reanalysis hourly historical weather; shown as monthly-hourly mean','movement':'Estimated pedestrian behavior','crowd':'Simulated; not live CCTV','forecast':'Heuristic, not trained or field-validated'}}
   if include_agents:result['agents']=[[round(a['x'],1),round(a['y'],1),a['phase']] for a in self.agents]
   return result
 def update(self,patch):
  schema={'target_crowd':(int,50,2000),'speed':(float,.2,60),'arrival_multiplier':(float,.1,5),'walking_speed':(float,.3,2.5),'dwell_minutes':(float,1,120),'site_share':(float,.01,.99),'month':(int,1,12),'hour':(int,0,23),'red_threshold':(float,75,150),'amber_threshold':(float,20,95),'seed':(int,1,999999),'year':(int,2021,2026)}
  with self.lock:
   for k,v in patch.items():
    if k in schema:
     cast,lo,hi=schema[k];v=cast(v)
     if not lo<=v<=hi:raise ValueError(f'{k} must be between {lo} and {hi}')
     if k=='year' and v not in (2021,2025,2026):raise ValueError('Year must be 2021, 2025 or 2026')
     self.config[k]=v
    elif k in ('festival','rain_override','diversion','gate_control','paused'):
     if not isinstance(v,bool):raise ValueError(f'{k} must be boolean')
     self.config[k]=v
   if self.config['amber_threshold']>=self.config['red_threshold']:raise ValueError('Amber threshold must be lower than red threshold')
   if any(k in patch for k in ('diversion','gate_control')):
    for a in self.agents:
     if a['phase'] in ('walking','exit') and a['index']<len(a['route']):
      # Re-route at next node, avoiding teleportation.
      start=a['route'][a['index']];end=a['route'][-1];a['route']=[start]+self.shortest(start,end)[1:];a['index']=1
    self.diverted+=1;self.events.appendleft({'at':round(self.clock),'type':'action','message':'Route intervention changed · paths recalculated'})
   return dict(self.config)

ENGINE=Engine()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):pass
 def reply(self,obj,status=200):
  data=json.dumps(obj,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/state':return self.reply(ENGINE.snapshot())
  if path=='/api/tourism':return self.reply({'tourism':TOURISM,'months':MONTHS})
  if path=='/api/health':return self.reply({'ok':True,'service':'YatraFlow Studio','version':'2.0'})
  if path=='/api/weather':return self.reply({'weather':WEATHER,'count':len(WEATHER['records'])})
  if path=='/api/export':return self.reply(ENGINE.snapshot(include_agents=False))
  if path=='/':path='/index.html'
  if path not in ('/index.html','/app.js','/style.css','/glass.css'):return self.reply({'error':'not found'},404)
  p=ROOT/'static'/path[1:];body=p.read_bytes();self.send_response(200);self.send_header('Content-Type',{'html':'text/html','js':'application/javascript','css':'text/css'}[p.suffix[1:]]);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>65536:raise ValueError('Request too large')
   payload=json.loads(self.rfile.read(length) or b'{}');path=urlparse(self.path).path
   if path=='/api/config':return self.reply({'ok':True,'config':ENGINE.update(payload)})
   if path=='/api/reset':ENGINE.reset();return self.reply({'ok':True})
   if path=='/api/alert':
    with ENGINE.lock:
     item=ENGINE.alerts.get(payload.get('id'))
     if not item:raise ValueError('Alert not found')
     action=payload.get('action')
     if action not in ('acknowledged','resolved'):raise ValueError('Invalid alert action')
     item['status']=action;item['ack_at' if action=='acknowledged' else 'resolved_at']=round(ENGINE.clock);item['note']=str(payload.get('note',''))[:200]
     ENGINE.events.appendleft({'at':round(ENGINE.clock),'type':'action','message':f"{item['zone']}: {action}"})
    return self.reply({'ok':True})
   return self.reply({'error':'not found'},404)
  except (ValueError,TypeError,KeyError) as e:return self.reply({'error':str(e)},400)

def loop():
 prev=time.monotonic()
 while True:
  time.sleep(.13);now=time.monotonic()
  try:ENGINE.step(now-prev)
  except Exception as e:print('Simulation error:',e)
  prev=now

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
 threading.Thread(target=loop,daemon=True).start()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);url=f'http://127.0.0.1:{args.port}'
 print('\n  YATRAFLOW / STUDIO 2.0\n  Local dashboard: '+url+'\n  Press Ctrl+C to stop.\n')
 if not args.no_browser:threading.Timer(.7,lambda:webbrowser.open(url)).start()
 try:server.serve_forever()
 except KeyboardInterrupt:print('\nStopping YatraFlow...')
 finally:server.server_close()
if __name__=='__main__':main()
