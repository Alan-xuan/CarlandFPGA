"""Render the taskbook's conceptual information-flow diagram, not a product screenshot."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

base=Path(__file__).parent
im=Image.new('RGB',(1800,900),'#f5f7fa'); d=ImageDraw.Draw(im)
font=lambda n,b=False:ImageFont.truetype(str(Path('C:/Windows/Fonts')/('msyhbd.ttc' if b else 'msyh.ttc')),n)
def text(x,y,s,size=28,color='#203145',bold=False):
    d.text((x,y),s,font=font(size,bold),fill=color)
def box(rect,title,lines,fill='#ffffff'):
    d.rounded_rectangle(rect,18,fill=fill,outline='#7c91a7',width=3)
    x,y=rect[:2];text(x+22,y+20,title,31,bold=True)
    for n,line in enumerate(lines):text(x+22,y+76+n*42,line,25)
def arrow(points,color='#2672a6',width=5):
    d.line(points,fill=color,width=width,joint='curve')
    x,y=points[-1];px,py=points[-2];a=math.atan2(y-py,x-px)
    p=[(x,y),(x-18*math.cos(a-.5),y-18*math.sin(a-.5)),(x-18*math.cos(a+.5),y-18*math.sin(a+.5))]
    d.polygon(p,fill=color)
text(40,18,'三维演示：信息边界与两种完整控制链路',36,bold=True)
box((40,85,540,230),'观众端 / 场景编辑器',['自由视角、实体障碍、蓝红门','锁定后只看，不把真图交给AI'],'#e8eff8')
box((40,300,540,550),'世界与传感权威',['隐藏布局、实体碰撞、运动积分','EM连续响应 / 振动等测量','只生成当前可获得的传感值'])
box((650,300,1150,550),'真实 FPGA 数据与执行链',['DAC → XADC → PL压缩/保护','实际 RS485 双向计费','HIL：三路输出 → 独立回采'])
box((1260,300,1760,550),'Ryzen AI PC 主规划端',['只读实际回传观测与里程计','风险识别 → 逐步建图 → 规划','yaw / pitch / speed / TTL'])
arrow([(290,230),(290,298)])
text(320,248,'真值仅供显示',24)
arrow([(540,390),(647,390)])
text(554,347,'测量',23)
arrow([(1150,390),(1257,390)])
text(1158,347,'遥测',23)
arrow([(1260,505),(1153,505)],'#b06c28')
text(1166,464,'决策',23,color='#9d5d1d')
arrow([(900,550),(900,660),(240,660),(240,553)],'#b06c28')
text(340,613,'主展示 HIL：经板端校验、输出及实际捕获后执行',26,color='#9d5d1d',bold=True)
arrow([(1520,550),(1520,785),(435,785),(435,553)],'#2b8062')
text(560,738,'PC_DIRECT 对照：有效板观测 → PC AI → 受限执行器',26,color='#236c53',bold=True)
text(650,96,'布局 / 网格 / 碰撞查询 / 未来数据',29,color='#9c3c3c',bold=True)
text(650,145,'不进入 AI 控制进程；结束后才解封评估',27,color='#9c3c3c')
text(40,847,'设计结构示意，非软件截图或已运行证据。300 / 9600 baud、HIL / PC直控分别测量和标记。',24,color='#536477')
im.save(base/'architecture_v4.png')
print(base/'architecture_v4.png')
