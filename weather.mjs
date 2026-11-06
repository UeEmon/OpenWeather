export const cities = {
 tokyo:{name:'相模湾沖',lat:35.0,lon:139.4},sapporo:{name:'石狩湾沖',lat:43.5,lon:141.0},sendai:{name:'三陸沖',lat:38.5,lon:142.5},nagoya:{name:'遠州灘',lat:34.3,lon:137.5},osaka:{name:'紀伊水道沖',lat:33.5,lon:135.0},hiroshima:{name:'土佐湾沖',lat:33.0,lon:133.5},fukuoka:{name:'玄界灘',lat:34.0,lon:130.0},naha:{name:'沖縄本島沖',lat:26.0,lon:127.0}
};
export function marineURL(city){return 'https://marine-api.open-meteo.com/v1/marine?'+new URLSearchParams({latitude:city.lat,longitude:city.lon,timezone:'Asia/Tokyo',current:'wave_height,wave_direction,wave_period,sea_surface_temperature',hourly:'wave_height,wave_direction,wave_period',forecast_days:'3'});}
export function describe(code,day=true){
 if(code===0)return [day?'☀':'☾',day?'晴れ':'快晴'];
 if([1,2].includes(code))return ['⛅','晴れ時々くもり'];
 if(code===3)return ['☁','くもり'];
 if([45,48].includes(code))return ['≋','霧'];
 if([71,73,75,77,85,86].includes(code))return ['❄','雪'];
 if([95,96,99].includes(code))return ['ϟ','雷雨'];
 if([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code))return ['☂','雨'];
 return ['—','不明'];
}
export function forecastURL(city){const p=new URLSearchParams({latitude:city.lat,longitude:city.lon,timezone:'Asia/Tokyo',current:'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m',hourly:'temperature_2m,precipitation_probability,weather_code,is_day',daily:'weather_code,temperature_2m_max,temperature_2m_min,sunset,precipitation_probability_max',wind_speed_unit:'ms',forecast_days:'7'});return `https://api.open-meteo.com/v1/forecast?${p}`;}
export function validate(data){if(!data?.current||!Number.isFinite(data.current.temperature_2m)||!Array.isArray(data.hourly?.time)||data.hourly.time.length<24||!Array.isArray(data.daily?.time)||data.daily.time.length!==7)throw Error('予報データの形式が正しくありません。');return data;}
