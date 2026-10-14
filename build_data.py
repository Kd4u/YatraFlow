"""One-time conversion of the user-provided Open-Meteo workbook to bundled JSON; not required at runtime."""
import zipfile, xml.etree.ElementTree as ET, json, datetime, pathlib
src=pathlib.Path('/mnt/data/open-meteo-24.71N84.98E125m.xlsx')
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(src) as z:
 root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
 rows=[]
 for row in root.findall('.//m:sheetData/m:row',ns):
  vals=[]
  for c in row:
   v=c.find('m:v',ns); inline=c.find('m:is/m:t',ns)
   vals.append((v.text if v is not None else (inline.text if inline is not None else '')) or '')
  rows.append(vals)
header=rows[3]
records=[]
for r in rows[4:]:
 try:
  dt=(datetime.datetime(1899,12,30)+datetime.timedelta(days=float(r[0]))).strftime('%Y-%m-%dT%H:%M')
  records.append([dt,round(float(r[1]),1),round(float(r[5]),2),round(float(r[2]),0),round(float(r[16]),1)])
 except (ValueError,IndexError):continue
out=pathlib.Path(__file__).with_name('weather_hourly.json')
out.write_text(json.dumps({'source':'Open-Meteo user-uploaded historical weather workbook','coordinates':[24.71,84.9839],'columns':['time','temperature_c','precipitation_mm','relative_humidity_pct','wind_speed_kmh'],'records':records},separators=(',',':')))
print(len(records),out.stat().st_size)
