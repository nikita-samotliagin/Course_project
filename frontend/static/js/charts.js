'use strict';
window.PulseCharts=(()=>{
 const colors=['#4659d4','#6cb9a3','#eab65c','#79a7dc','#e58187','#b3a3d8'];
 function create(canvas,type,data){
  const ctx=canvas.getContext('2d');let points=[],active=-1;
  const rub=v=>(v/100).toLocaleString('ru-RU',{maximumFractionDigits:2})+' руб.';
  function render(){
   const w=Math.max(250,canvas.clientWidth),h=canvas.clientHeight||280,dpr=window.devicePixelRatio||1;
   canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);ctx.font='11px Arial';points=[];
   if(type==='line'){
    const pad={l:60,r:18,t:20,b:38},pw=w-pad.l-pad.r,ph=h-pad.t-pad.b,max=Math.max(100,...data.map(x=>x.revenue_cents));
    ctx.strokeStyle='#e9edf4';ctx.fillStyle='#758097';ctx.textAlign='right';
    for(let i=0;i<=4;i++){const y=pad.t+ph-i*ph/4;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText((max*i/4/100).toLocaleString('ru-RU',{maximumFractionDigits:2}),pad.l-8,y+4);}
    points=data.map((r,i)=>({x:pad.l+(data.length===1?pw/2:i*pw/(data.length-1)),y:pad.t+ph-r.revenue_cents/max*ph,row:r}));
    ctx.fillStyle='#4659d420';ctx.beginPath();ctx.moveTo(points[0]?.x||pad.l,pad.t+ph);points.forEach(p=>ctx.lineTo(p.x,p.y));ctx.lineTo(points.at(-1)?.x||pad.l,pad.t+ph);ctx.closePath();ctx.fill();
    ctx.strokeStyle=colors[0];ctx.lineWidth=2.5;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
    if(points.length===1){ctx.fillStyle=colors[0];ctx.beginPath();ctx.arc(points[0].x,points[0].y,4,0,2*Math.PI);ctx.fill();}
    ctx.fillStyle='#758097';ctx.textAlign='center';const step=Math.max(1,Math.ceil(data.length/6));points.forEach((p,i)=>{if(i%step===0||i===points.length-1)ctx.fillText(p.row.date.slice(8)+'.'+p.row.date.slice(5,7),p.x,h-10);});
    if(active>=0&&points[active]){const p=points[active];ctx.fillStyle=colors[0];ctx.beginPath();ctx.arc(p.x,p.y,5,0,2*Math.PI);ctx.fill();const x=Math.min(Math.max(5,p.x-85),w-185),y=Math.max(3,p.y-55);ctx.fillStyle='#18233f';ctx.fillRect(x,y,180,44);ctx.fillStyle='white';ctx.textAlign='left';ctx.fillText(p.row.date,x+10,y+16);ctx.fillText(rub(p.row.revenue_cents),x+10,y+34);}
   }else if(type==='bar'){
    const max=Math.max(1,...data.map(x=>x.revenue_cents)),gap=50;
    if(!data.length){ctx.fillStyle='#758097';ctx.textAlign='center';ctx.fillText('Нет выполненных заказов',w/2,h/2);return;}
    data.forEach((row,i)=>{const y=20+i*gap;ctx.fillStyle='#758097';ctx.textAlign='left';ctx.fillText(row.name,0,y);ctx.fillStyle='#eff2fa';ctx.fillRect(0,y+10,w-65,12);ctx.fillStyle=colors[i%colors.length];ctx.fillRect(0,y+10,(w-65)*row.revenue_cents/max,12);ctx.fillStyle='#16213d';ctx.textAlign='right';ctx.fillText((row.revenue_cents/100).toLocaleString('ru-RU'),w,y+21);});
   }else{
    const total=data.reduce((sum,row)=>sum+row.count,0),cx=w/2,cy=h/2,r=Math.min(w,h)/2-20;let angle=-Math.PI/2;
    if(!total){ctx.strokeStyle='#e9edf4';ctx.lineWidth=25;ctx.beginPath();ctx.arc(cx,cy,r-15,0,2*Math.PI);ctx.stroke();}
    else data.forEach((row,i)=>{if(!row.count)return;const end=angle+row.count/total*2*Math.PI;ctx.beginPath();ctx.arc(cx,cy,r,angle,end);ctx.arc(cx,cy,r-28,end,angle,true);ctx.closePath();ctx.fillStyle=colors[i];ctx.fill();angle=end;});
    ctx.fillStyle='#16213d';ctx.textAlign='center';ctx.font='bold 31px Arial';ctx.fillText(total,cx,cy+4);ctx.font='11px Arial';ctx.fillStyle='#758097';ctx.fillText('заказов в выборке',cx,cy+27);
   }
  }
  const observer=new ResizeObserver(render);observer.observe(canvas);render();
  canvas.onmousemove=type==='line'?event=>{const rect=canvas.getBoundingClientRect();const x=event.clientX-rect.left;active=points.reduce((best,p,i)=>best<0||Math.abs(p.x-x)<Math.abs(points[best].x-x)?i:best,-1);render();}:null;
  canvas.onmouseleave=()=>{active=-1;render();};
  return {destroy(){observer.disconnect();canvas.onmousemove=null;canvas.onmouseleave=null;},download(){canvas.toBlob(blob=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='pulse-'+type+'.png';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);},'image/png');}};
 }
 return {create,colors};
})();
