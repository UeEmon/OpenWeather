export function sampleBathymetry(grid,lon,lat){
 if(!grid?.latitude?.length||!grid.longitude?.length)return null;
 const ys=grid.latitude,xs=grid.longitude,rows=ys.length,cols=xs.length;
 const dx=(xs[cols-1]-xs[0])/(cols-1),dy=(ys[rows-1]-ys[0])/(rows-1);
 if(!grid.global&&(lat<ys[0]||lat>ys[rows-1]||lon<xs[0]||lon>xs[cols-1]))return null;
 let x=(lon-xs[0])/dx,y=(lat-ys[0])/dy;
 if(grid.global)x=((x%cols)+cols)%cols;else x=Math.max(0,Math.min(cols-1,x));
 y=Math.max(0,Math.min(rows-1,y));const x0=Math.floor(x),y0=Math.floor(y),x1=grid.global?(x0+1)%cols:Math.min(cols-1,x0+1),y1=Math.min(rows-1,y0+1),fx=x-x0,fy=y-y0;
 const at=(r,c)=>grid.height_m[r*cols+c],v=[at(y0,x0),at(y0,x1),at(y1,x0),at(y1,x1)];
 if(v.some(n=>typeof n!=='number'||!Number.isFinite(n)))return null;
 return (v[0]*(1-fx)+v[1]*fx)*(1-fy)+(v[2]*(1-fx)+v[3]*fx)*fy;
}
export function depthColor(height){if(height===null||height>=0)return [0,0,0,0];const t=Math.min(1,-height/7000);return [Math.round(125*(1-t)),Math.round(206*(1-t)+32*t),Math.round(220*(1-t)+91*t),230];}
