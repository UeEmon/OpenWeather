export const SETTINGS_KEY='umibiyori-browser-settings-v1';
export function readSettings(storage){try{const d=JSON.parse(storage.getItem(SETTINGS_KEY)||'{}');return d&&typeof d==='object'&&!Array.isArray(d)?d:{};}catch{return {};}}
export function writeSettings(storage,patch){const next={...readSettings(storage),...patch};storage.setItem(SETTINGS_KEY,JSON.stringify(next));return next;}
export function validLocalArea(a){const b=a?.bounds;return typeof a?.name==='string'&&a.name.length>0&&a.name.length<=60&&b&&['south','west','north','east'].every(k=>typeof b[k]==='number'&&Number.isFinite(b[k]))&&b.south>=-90&&b.north<=90&&b.south<b.north&&b.west>=-180&&b.east<=180&&b.west<b.east&&b.east-b.west<=180;}
