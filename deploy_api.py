import paramiko, io

NEW_SERVER = """#!/usr/bin/env python3
import json, time, os
from http.server import BaseHTTPRequestHandler, HTTPServer

_prev_cpu = None
_prev_net = None

def cpu_usage():
    global _prev_cpu
    with open('/proc/stat') as f:
        lines = f.readlines()
    cores = []
    for ln in lines:
        if ln.startswith('cpu') and len(ln) > 4 and ln[3] != ' ':
            p = list(map(int, ln.split()[1:8]))
            cores.append(p)
    usage = [0.0] * len(cores)
    if _prev_cpu:
        for i,(c,p) in enumerate(zip(cores,_prev_cpu)):
            idle_c = c[3]+c[4]; idle_p = p[3]+p[4]
            td = sum(c)-sum(p)
            if td > 0:
                usage[i] = round((1-(idle_c-idle_p)/td)*100, 1)
    _prev_cpu = cores
    return usage

def cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip())/1000, 1)
    except:
        return 0.0

def memory():
    m = {}
    with open('/proc/meminfo') as f:
        for ln in f:
            k,*v = ln.split()
            if k in ('MemTotal:','MemFree:','MemAvailable:'):
                m[k[:-1]] = int(v[0])
    tot = m.get('MemTotal',1); avail = m.get('MemAvailable',0)
    used = tot - avail
    return {'total_mb':round(tot/1024,1),'used_mb':round(used/1024,1),
            'free_mb':round(avail/1024,1),'percent':round(used/tot*100,1)}

def network():
    global _prev_net
    rx = tx = 0
    with open('/proc/net/dev') as f:
        for ln in f:
            if 'eth0:' in ln:
                p = ln.split(); rx=int(p[1]); tx=int(p[9])
    now = time.time()
    rx_kbps = tx_kbps = 0.0
    if _prev_net:
        dt = now - _prev_net['t']
        if dt > 0:
            rx_kbps = round((rx-_prev_net['rx'])/dt/1024, 2)
            tx_kbps = round((tx-_prev_net['tx'])/dt/1024, 2)
    _prev_net = {'rx':rx,'tx':tx,'t':now}
    return {'rx_mb':round(rx/1048576,2),'tx_mb':round(tx/1048576,2),
            'rx_kbps':max(0,rx_kbps),'tx_kbps':max(0,tx_kbps)}

def storage():
    try:
        r = os.popen('df / --output=size,used,avail,pcent 2>/dev/null').read()
        p = r.strip().split('\\n')[1].split()
        return {'total_gb':round(int(p[0])/1048576,1),
                'used_gb':round(int(p[1])/1048576,1),
                'free_gb':round(int(p[2])/1048576,1),
                'percent':int(p[3].replace('%',''))}
    except:
        return {}

def uptime():
    with open('/proc/uptime') as f:
        s = float(f.read().split()[0])
    h=int(s//3600); m=int((s%3600)//60); sc=int(s%60)
    return {'seconds':int(s),'formatted':'%02d:%02d:%02d'%(h,m,sc)}

def load_avg():
    with open('/proc/loadavg') as f:
        p = f.read().split()
    return {'1m':float(p[0]),'5m':float(p[1]),'15m':float(p[2])}

def col(text, color):
    palette = {'red':'#ff5555','green':'#55ff55','yellow':'#ffff55',
               'cyan':'#55ffff','white':'#cccccc','gray':'#777777',
               'orange':'#ffaa00'}
    c = palette.get(color, color)
    return '<span style="color:%s">%s</span>' % (c, text)

def armbian_motd(d):
    cpu_avg = sum(d['cpu']['usage']) / max(len(d['cpu']['usage']),1)
    tmp      = d['cpu']['temp_c']
    mem_pct  = d['memory']['percent']
    mem_total= d['memory']['total_mb']
    disk_pct = d['storage'].get('percent', 0)
    disk_tot = d['storage'].get('total_gb', 0)
    up       = d['uptime']['formatted']
    load1    = d['load']['1m']
    ip       = '192.168.2.119'

    tc = 'green' if tmp < 55 else ('yellow' if tmp < 70 else 'red')
    cc = 'green' if cpu_avg < 60 else ('yellow' if cpu_avg < 85 else 'red')
    mc = 'green' if mem_pct < 60 else ('yellow' if mem_pct < 85 else 'red')

    cores_str = '  '.join([str(round(v,1))+'%' for v in d['cpu']['usage']])
    net_str   = 'RX: '+str(d['network']['rx_kbps'])+' KB/s  TX: '+str(d['network']['tx_kbps'])+' KB/s'

    rows = [
        col('  _   ___   ___   ___   ___      ___   ___   _    ___ ', 'cyan'),
        col(' | | | __| / __| / __| | __|   | _ \\| __| (_)  / __|', 'cyan'),
        col('_| | | _|  \\__ \\ \\__ \\ | _|    |   / | _|  | |  \\__ \\ ', 'cyan'),
        col('\\__| |___| |___/ |___| |___|   |_|_\\ |___| |_|  |___/', 'cyan'),
        '',
        ' Welcome to ' + col('Armbian 21.08.8','cyan') + '  with ' + col('Linux 4.4.194-rk322x','green'),
        '',
        (' System load:   ' + col(str(round(load1,2)), cc)
         + '                Up time:    ' + col(up,'green')),
        (' Memory usage:  ' + col(str(round(mem_pct,1))+'%', mc)
         + ' of ' + col(str(round(mem_total))+'M','white')),
        (' CPU temp:      ' + col(str(tmp)+'&deg;C', tc)
         + '             Usage of /:  ' + col(str(disk_pct)+'% of '+str(disk_tot)+'G','green')),
        '',
        ' ' + col('[ Cores: ' + cores_str + ' ]', 'gray'),
        ' ' + col('[ ' + net_str + ' ]', 'gray'),
        '',
        ' ' + col('root@rk322x-box','green') + ':' + col('~#','white') + ' ' + col('&#9646;','white'),
    ]
    return '\\n'.join(rows)

def get_data():
    return {'cpu':{'usage':cpu_usage(),'temp_c':cpu_temp()},
            'memory':memory(),'network':network(),
            'storage':storage(),'uptime':uptime(),'load':load_avg()}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/motd':
            d = get_data()
            body = armbian_motd(d).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith('/api'):
            body = json.dumps(get_data()).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == '/api/reboot':
            # Bloquear se veio pela Cloudflare (internet) — header CF-Connecting-IP presente
            # Ou se o IP direto não for local
            cf_ip = self.headers.get('CF-Connecting-IP', '')
            client_ip = self.client_address[0]
            local = (not cf_ip and
                     (client_ip.startswith('192.168.') or
                      client_ip.startswith('10.')      or
                      client_ip.startswith('127.')     or
                      client_ip == '::1'))
            if not local:
                self.send_response(403)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(b'{"error":"forbidden"}')
                return
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(b'{"status":"rebooting"}')
            import threading
            threading.Timer(1.0, lambda: os.system('reboot')).start()
        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.end_headers()

    def log_message(self, *a): pass

if __name__ == '__main__':
    cpu_usage(); time.sleep(0.5)
    print('RK3229 API :8080')
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.2.119', username='root', password='conputador', timeout=10)

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(NEW_SERVER.encode('utf-8')), '/opt/rk3229api/server.py')
sftp.close()
print('server.py enviado')

stdin, stdout, stderr = client.exec_command(
    'systemctl restart rk3229api && sleep 2 && systemctl is-active rk3229api')
print('Status:', stdout.read().decode().strip())

stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8080/api/motd')
motd = stdout.read().decode('utf-8', 'replace')
print('MOTD OK, tamanho:', len(motd), 'chars')
print(motd[:300])

client.close()
