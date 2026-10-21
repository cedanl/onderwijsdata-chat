// Donkere tegenhangers van de lichte kleuren die tools/plot.py in de figuur bakt (#567): titel,
// raster, aslijnen, legenda en een zwarte reeks. Per genest object samengevoegd, zodat
// titeltekst, astitels, tickformat enz. blijven; alleen kopieën, de figuur zelf blijft ongemoeid.
// Eén definitie voor rapport en dashboard (#574). Het is broncode voor een inline <script>, dus
// de backslash in de regex staat dubbel (\\d) in deze template literal.
export const DARK_FIGURE_JS = `function _o(v){return !!v&&typeof v==='object'&&!Array.isArray(v)}
function _w(o,p){return Object.assign({},o,p)}
function _c(v){return Array.isArray(v)?v.map(_c):typeof v==='string'&&/^(#000000|#000|black)$/i.test(v.trim())?'#F9FAFB':v}
function _r(o,ks){o=_w(o);ks.forEach(function(k){if(k in o)o[k]=_c(o[k])});return o}
function _dl(l){var t=l.title;if(_o(t))l.title=_w(t,{font:_w(t.font,{color:'#F9FAFB'})});
Object.keys(l).forEach(function(k){if(/^[xy]axis\\d*$/.test(k)&&_o(l[k]))l[k]=_w(l[k],{gridcolor:'#374151',linecolor:'#4B5563'})});
if(_o(l.legend))l.legend=_w(l.legend,{bgcolor:'rgba(31,41,55,0.8)',bordercolor:'#374151'});return l}
function _dd(d){return Array.isArray(d)?d.map(function(t){if(!_o(t))return t;t=_w(t);if(_o(t.marker))t.marker=_r(t.marker,['color','colors']);if(_o(t.line))t.line=_r(t.line,['color']);return t}):d}`
