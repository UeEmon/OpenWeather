// GSI DEM PNG: https://maps.gsi.go.jp/development/ichiran.html
// Heights are centimetres in signed 24-bit RGB; 0x800000 denotes no data.
export function decodeGsiHeight(r,g,b,alpha=255){
 let value=r*65536+g*256+b;
 if(value===8388608||alpha===0)return 0;
 if(value>8388608)value-=16777216;
 return value/100;
}
