(function(){
var DATA="https://raw.githubusercontent.com/vencacapital/tvr-commodities/refs/heads/main/data/commodities.json";
var MACRO="https://thevencareport.com/dashboard/";
var CSS="#tvrc{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:1180px;margin:0 auto;font-size:14px}"
+"#tvrc *{box-sizing:border-box}"
+"#tvrc .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin-bottom:18px;padding-bottom:12px;border-bottom:2px solid #1a1a1a}"
+"#tvrc .stamp{font-size:12px;color:#666}"
+"#tvrc .macrolink{display:inline-block;padding:7px 14px;background:#1a1a1a;color:#fff !important;text-decoration:none !important;border-radius:3px;font-size:12px;font-weight:600;letter-spacing:.04em}"
+"#tvrc .movers{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:22px}"
+"#tvrc .mcard{border:1px solid #e0e0e0;border-radius:4px;padding:14px 16px}"
+"#tvrc .mcard h4{margin:0 0 10px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:#666;font-weight:700}"
+"#tvrc .mrow{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f2f2f2;font-size:13px}"
+"#tvrc .mrow:last-child{border-bottom:none}"
+"#tvrc .filters{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}"
+"#tvrc .filters button{padding:6px 13px;border:1px solid #ccc;background:#fff;border-radius:3px;cursor:pointer;font-size:12px;font-weight:600;color:#444}"
+"#tvrc .filters button.on{background:#1a1a1a;color:#fff;border-color:#1a1a1a}"
+"#tvrc .wrap{overflow-x:auto;border:1px solid #e0e0e0;border-radius:4px}"
+"#tvrc table{width:100%;border-collapse:collapse;min-width:980px}"
+"#tvrc th{background:#f7f7f7;padding:10px 9px;text-align:right;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#555;border-bottom:1px solid #ddd;cursor:pointer;white-space:nowrap;font-weight:700}"
+"#tvrc th:first-child{text-align:left}"
+"#tvrc th:hover{background:#ededed}"
+"#tvrc td{padding:9px;text-align:right;border-bottom:1px solid #f2f2f2;white-space:nowrap;font-variant-numeric:tabular-nums}"
+"#tvrc td:first-child{text-align:left;font-weight:600}"
+"#tvrc tr:hover td{background:#fafafa}"
+"#tvrc .grp{font-size:10px;color:#999;font-weight:400;display:block;letter-spacing:.05em;text-transform:uppercase}"
+"#tvrc .pos{color:#0a7d3e;font-weight:600}"
+"#tvrc .neg{color:#c0392b;font-weight:600}"
+"#tvrc .nil{color:#bbb}"
+"#tvrc .pct{display:inline-block;min-width:34px;padding:2px 5px;border-radius:3px;font-size:12px;font-weight:600}"
+"#tvrc .note{margin-top:14px;font-size:11px;color:#777;line-height:1.65}"
+"#tvrc .note b{color:#444}"
+"@media(max-width:700px){#tvrc .movers{grid-template-columns:1fr}}";

var st=document.createElement("style");
st.appendChild(document.createTextNode(CSS));
document.head.appendChild(st);

var el=document.getElementById("tvrc");
if(!el){return;}
var D=null,filt="All",sortK="group",sortD=1;
el.innerHTML='<p style="color:#888">Loading commodity data...</p>';

function num(v,d){if(v===null||v===undefined)return null;return Number(v).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});}
function sign(v,d){if(v===null||v===undefined)return '<span class="nil">&ndash;</span>';var c=v>0?"pos":(v<0?"neg":"");var s=v>0?"+":"";return '<span class="'+c+'">'+s+num(v,d===undefined?2:d)+'%</span>';}
function band(v){if(v===null||v===undefined)return '<span class="nil">&ndash;</span>';var bg="#f0f0f0",fg="#444";if(v>=80){bg="#fde8e4";fg="#c0392b";}else if(v<=20){bg="#e4f4ea";fg="#0a7d3e";}return '<span class="pct" style="background:'+bg+';color:'+fg+'">'+Math.round(v)+'</span>';}

function movers(rows){
var v=rows.filter(function(r){return r.chg_1w!==null&&r.chg_1w!==undefined;}).slice().sort(function(a,b){return b.chg_1w-a.chg_1w;});
function list(arr){return arr.map(function(r){return '<div class="mrow"><span>'+r.name+'</span>'+sign(r.chg_1w)+'</div>';}).join("");}
return '<div class="movers"><div class="mcard"><h4>Biggest gainers &middot; 1 week</h4>'+list(v.slice(0,5))+'</div><div class="mcard"><h4>Biggest decliners &middot; 1 week</h4>'+list(v.slice(-5).reverse())+'</div></div>';
}

function table(){
var rows=D.rows.filter(function(r){return filt==="All"||r.group===filt;});
var ord=["Energy","Metals","Grains","Softs","Livestock"];
rows.sort(function(a,b){
 if(sortK==="group"){var d=ord.indexOf(a.group)-ord.indexOf(b.group);return d!==0?d:a.name.localeCompare(b.name);}
 if(sortK==="name")return sortD*a.name.localeCompare(b.name);
 var x=a[sortK],y=b[sortK];
 if(x===null||x===undefined)return 1;
 if(y===null||y===undefined)return -1;
 return sortD*(y-x);
});
var h=["name|Instrument","last|Last","chg_1w|1W %","chg_1m|1M %","vs_3y|vs 3Y avg","vs_5y|vs 5Y avg","rank_5y|5Y %ile","seas_avg|Seas. avg","seas_hit|Seas. hit","cot_net|COT net","cot_rank_3y|COT %ile"];
var t='<div class="wrap"><table><thead><tr>'+h.map(function(c){var p=c.split("|");return '<th data-k="'+p[0]+'">'+p[1]+'</th>';}).join("")+'</tr></thead><tbody>';
rows.forEach(function(r){
t+='<tr><td>'+r.name+'<span class="grp">'+r.group+'</span></td>'
+'<td>'+(num(r.last,2)||'<span class="nil">&ndash;</span>')+'</td>'
+'<td>'+sign(r.chg_1w)+'</td>'
+'<td>'+sign(r.chg_1m)+'</td>'
+'<td>'+sign(r.vs_3y,1)+'</td>'
+'<td>'+sign(r.vs_5y,1)+'</td>'
+'<td>'+band(r.rank_5y)+'</td>'
+'<td>'+sign(r.seas_avg,2)+'</td>'
+'<td>'+(r.seas_hit===null||r.seas_hit===undefined?'<span class="nil">&ndash;</span>':Math.round(r.seas_hit)+'%')+'</td>'
+'<td>'+(r.cot_net===null||r.cot_net===undefined?'<span class="nil">&ndash;</span>':num(r.cot_net,0))+'</td>'
+'<td>'+band(r.cot_rank_3y)+'</td></tr>';
});
return t+'</tbody></table></div>';
}

function draw(){
var cotd="";
for(var i=0;i<D.rows.length;i++){if(D.rows[i].cot_date){cotd=D.rows[i].cot_date;break;}}
var groups=["All","Energy","Metals","Grains","Softs","Livestock"];
el.innerHTML='<div class="bar"><div><div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#666;font-weight:700">Commodity Monitor</div><div class="stamp">Prices to '+(D.rows[0]?D.rows[0].asof:"")+' &middot; COT to '+cotd+' &middot; Built '+D.generated_utc+'</div></div><a class="macrolink" href="'+MACRO+'">Macro Dashboard &rarr;</a></div>'
+movers(D.rows)
+'<div class="filters">'+groups.map(function(g){return '<button data-g="'+g+'" class="'+(g===filt?"on":"")+'">'+g+'</button>';}).join("")+'</div>'
+table()
+'<div class="note"><b>1W / 1M %</b> are changes over the past week and month, measured to the nearest prior trading day. <b>vs 3Y / 5Y avg</b> is the current price against its average daily close over that period. <b>5Y %ile</b> is where the price sits within its five-year range, 0 being the low and 100 the high. <b>Seas. avg</b> is the average return for '+D.month+' across the last 15 years, and <b>Seas. hit</b> the share of those years that finished higher. <b>COT net</b> is managed money net futures positioning from the CFTC Disaggregated report, and <b>COT %ile</b> its rank against the last three years. Prices are front-month futures continuations and may include contract roll effects. Seasonality and positioning describe past behaviour and are not forecasts.</div>';

var bs=el.querySelectorAll(".filters button");
for(var a=0;a<bs.length;a++){bs[a].onclick=function(){filt=this.getAttribute("data-g");draw();};}
var ths=el.querySelectorAll("th");
for(var b=0;b<ths.length;b++){ths[b].onclick=function(){var k=this.getAttribute("data-k");if(sortK===k){sortD=-sortD;}else{sortK=k;sortD=1;}draw();};}
}

fetch(DATA+"?v="+Math.floor(Date.now()/300000))
.then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
.then(function(j){D=j;draw();})
.catch(function(e){el.innerHTML='<p style="color:#c0392b">Could not load data: '+e.message+'</p>';});
})();
