// Een kaart in een rapport of gedownload dashboard (#642). Maplibre, waarmee Plotly een `choroplethmap` tekent, start
// een worker vanaf een blob:-URL, en dat lukt niet in een frame zonder eigen origin: het rapport staat in een sandbox
// zonder allow-same-origin (#634), en een bestand van schijf heeft er ook geen. De kaart bleef daar leeg ("Worker failed
// to load"; gemeten: zonder sandbox of mét allow-same-origin tekende dezelfde kaart wel). Dit script, direct na Plotly,
// tekent zo'n kaart als `choropleth` op een geo-subplot: dezelfde gebieden, kleuren en hoverlabels, als SVG zonder
// worker en zonder tegels, passend op de gebieden (fitbounds). De chat zelf houdt maplibre.
// Ook voor een rapport van vóór deze build: de viewer zet dit script achter Plotly (plotlyBron.js, metEigenPlotly).
// De geo-kaart tekent met d3, en d3 wil de buitenring van een vlak met de klok mee (GeoJSON zegt ertegenin): anders
// kleurt hij de rest van de wereld. Elke ring gaat daarom de goede kant op, in een kopie van de GeoJSON.
// Een geo-subplot haalt ook met visible:false een wereldkaart van cdn.plot.ly (world_110m.json) en tekent pas daarna;
// de policy van het rapport houdt dat tegen (geen derde partij, #486). Plotly kijkt eerst in PlotlyGeoAssets: daar
// staat een lege wereld, want de kaart toont alleen haar eigen gebieden.
// Een tik op een gebied toont naam en waarde (#655). In een los bestand stuurt de browser na de klik van een tik ook
// mouseout, en Plotly haalt het label dan meteen weer weg (in het rapportframe gaat die mouseout naar de app eromheen).
// Haalt Plotly het label vlak na een klik weg, dan beweegt het script nog één keer over de getikte plek.
export const KAART_ALS_SVG_JS = `(function(){var P=window.Plotly;if(!P||P.__kaartAlsSvg)return;P.__kaartAlsSvg=true;
var A=window.PlotlyGeoAssets=window.PlotlyGeoAssets||{},T=A.topojson=A.topojson||{},leeg={type:'GeometryCollection',geometries:[]};
T.world_110m=T.world_110m||{type:'Topology',arcs:[],objects:{land:leeg,ocean:leeg,lakes:leeg,rivers:leeg,countries:leeg,coastlines:leeg,subunits:leeg}};
function mee(r){var s=0;for(var i=0;i<r.length-1;i++)s+=(r[i+1][0]-r[i][0])*(r[i+1][1]+r[i][1]);return s>0}
function vlak(v){return v.map(function(r,i){return (i===0)!==mee(r)?r.slice().reverse():r})}
function d3vorm(gj){return Object.assign({},gj,{features:(gj&&gj.features||[]).map(function(f){var g=f&&f.geometry;if(!g)return f;
var c=g.type==='Polygon'?vlak(g.coordinates):g.type==='MultiPolygon'?g.coordinates.map(vlak):g.coordinates;
return Object.assign({},f,{geometry:Object.assign({},g,{coordinates:c})})})})}
function geo(d,l){if(!Array.isArray(d)||!d.some(function(t){return t&&t.type==='choroplethmap'}))return;
d.forEach(function(t){if(t&&t.type==='choroplethmap'){t.type='choropleth';t.geo='geo';t.geojson=d3vorm(t.geojson);delete t.subplot;delete t.below}});
l.geo=Object.assign({fitbounds:'locations',visible:false,projection:{type:'mercator'},bgcolor:'rgba(0,0,0,0)'},l.geo,{scope:'world',resolution:110});delete l.map;return true}
function tik(gd){if(!gd||typeof gd.on!=='function'||gd.__kaartTik)return;gd.__kaartTik=true;var q=null,t=0;
gd.on('plotly_click',function(e){var v=e&&e.event;q=v?{x:v.clientX,y:v.clientY}:null;t=Date.now()});
gd.on('plotly_unhover',function(){if(!q||Date.now()-t>500)return;var p=q;q=null;setTimeout(function(){
var el=document.elementFromPoint(p.x,p.y);if(el)el.dispatchEvent(new MouseEvent('mousemove',{clientX:p.x,clientY:p.y,bubbles:true}))},0)})}
['newPlot','react'].forEach(function(n){var f=P[n];if(typeof f!=='function')return;P[n]=function(gd,d,l,c){var k;
try{if(d&&!Array.isArray(d)&&d.data){d.layout=d.layout||{};k=geo(d.data,d.layout)}else{l=l||{};k=geo(d,l)}}catch(e){}
var r=f.call(this,gd,d,l,c);if(k&&r&&typeof r.then==='function')r.then(tik);return r}})})()`

export const kaartAlsSvgScript = () => `<script>${KAART_ALS_SVG_JS}</script>`

// Heeft deze HTML het script al (een rapport van deze build)? Dan niet nog eens.
export const heeftKaartAlsSvg = html => String(html ?? '').includes('__kaartAlsSvg')
