from pathlib import Path
from PIL import Image,ImageDraw
import math
root=Path(__file__).resolve().parent.parent/'assets';S=4
im=Image.new('RGBA',(256*S,256*S));d=ImageDraw.Draw(im)
def pts(p):return [(int(x*S),int(y*S)) for x,y in p]
def line(p,fill,width):d.line(pts(p),fill=fill,width=width*S,joint='curve')
d.rounded_rectangle((8*S,8*S,248*S,248*S),radius=55*S,fill='#352035')
d.rounded_rectangle((14*S,14*S,242*S,242*S),radius=50*S,outline='#805263',width=2*S)
# A radiant four-point star above an open book; deliberately simple at 16 px.
d.polygon(pts([(128,41),(138,68),(164,78),(138,88),(128,115),(118,88),(92,78),(118,68)]),fill='#F5C879')
line([(76,57),(86,67)],'#C38C4C',4);line([(180,57),(170,67)],'#C38C4C',4)
left=[(51,126),(70,120),(91,124),(111,133),(128,146),(128,207),(110,195),(91,187),(70,183),(51,188)]
right=[(256-x,y) for x,y in left]
d.polygon(pts(left),fill='#FFF0D2');d.polygon(pts(right),fill='#E5B56E')
line([(128,148),(128,208)],'#352035',4)
line([(61,198),(85,197),(108,204),(128,216),(148,204),(171,197),(195,198)],'#F5C879',5)
line([(66,142),(87,141),(110,153)],'#C38C4C',3);line([(66,158),(87,157),(110,169)],'#C38C4C',3)
im=im.resize((256,256),Image.Resampling.LANCZOS)
im.save(root/'xuguang-icon.png');im.save(root/'xuguang.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
