import os
import machine
import network
import utime
import usocket
import _thread

nic     = None  # Network interface controller
s_web   = None  # Socket for web server

svNCID  = 0     # Next call id
lkNCID  = _thread.allocate_lock()

uart    = None  # Communication device with RP2040
lkUART  = _thread.allocate_lock()

svRPCResponses = {}    # Dic with RPC responses received
lkRPCResponses = _thread.allocate_lock()

def setup():
	setupUART()
	setupWiFi()
	setupSockets()
# end def


def setupWiFi():
	global nic
	# Enable interface as WiFi access point
	nic = network.WLAN(network.AP_IF)
	nic.active(False)
	nic.config(
		ssid='Sensor',
		# channel=11,
		# security=network.AUTH_OPEN, # Open
		security=network.AUTH_WPA2_PSK, # WPA2-PSK
		key='12345678',
		# hostname='Sensor'
	)
	nic.active(True)
	nic.ifconfig(('192.168.1.1', '255.255.255.0', '192.168.1.1', '192.168.1.1'))
	network.hostname('Sensor')
# end def


def setupSockets():
	global s_web
	while not nic.active():
		utime.sleep(0.25)
	print('AP initialized successfully')
	s_web  = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
	ip  = nic.ifconfig()[0]
	s_web.bind( (ip, 80) )
	s_web.listen()
	print(f'Listening on {ip}:80')
# end def


def setupUART():
	global uart
	pin_tx = machine.Pin(17, machine.Pin.OUT)
	pin_rx = machine.Pin(16, machine.Pin.IN)
	uart   = machine.UART(2,
		baudrate=115200,
		tx=17, rx=16,
		timeout=1,
		timeout_char=1)
# end def

# ## ##################################
# Functions
# ## ##################################

def fetchUriParams(sreq):
	print(f'fetchUriParams over {sreq}')
	up = {}
	qmpos = indexOf(sreq, '?')
	if qmpos == -1:
		print('up:', up)
		return up
	parts = sreq[qmpos+1:].split('&')
	for p in parts:
		pparts = p.split('=', 2)
		key = pparts[0]
		value = pparts[1] if len(pparts) > 1 else None
		up[key] = value
	print('up:', up)
	return up
# end def


def indexOf(s, c, offset=0):
	for i in range(offset, len(s)):
		if s[i] == c:
			return i
	return -1
# end def


def rpcReqS( func, *args ):
	'''Sends a Request for RPC'''
	global lkNCID, svNCID
	print('rpcReqS args: ', args)
	# 1. Validate function signature
	if not isinstance(func, str): return None
	if args:
		sparams = ','.join( [str(a) for a in args] )
	else:
		sparams = ''

	# 2. Generate unique call Id (numeric autoincrement)
	with lkNCID:
		cid = svNCID
		svNCID+= 1

	# 3. Send RPC call request
	# An rpc call is:
	# id:functionName:commaSeparatedParams
	reqid = f'{cid}:{func}'
	with lkUART:
		uart.write(f'{reqid}:{sparams}\n')
	print(f'UART <= {reqid}:{sparams}')
	return reqid
# end def


def rpcResW( reqid, timeout=1000 ):
	'''Awaits for the respose of an RPC request'''
	# An rpc respose is:
	# id:functionName:result
	elapsed = 0
	while elapsed < timeout:
		with lkRPCResponses:
			if reqid in svRPCResponses:
				r = svRPCResponses[reqid]
				del svRPCResponses[reqid]
				return r

		utime.sleep(0.001)
		elapsed+= 1
	print(f'rpcResW: {reqid} not in {svRPCResponses}' )
	return None
# end def


def rpc( func, *args ):
	'''Performs a blocking RPC call'''
	reqid = rpcReqS( func, *args )
	return rpcResW( reqid )
# end def

def serveTemp(sreq):
	temp = rpc('temp')
	if temp is None:
		return ''
	return f'{float(temp):.3f}'
# end def

def serveLvl(sreq):
	lvl = rpc('lvl')
	if lvl is None:
		return ''
	return lvl

def serveHeat(sreq):
	heat = rpc('heat')
	if heat is None:
		return ''
	return heat

def serveInP(sreq):
	inP = rpc('inP')
	if inP is None:
		return ''
	return inP

def serveLed(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('led', up['on'])
	else:
		status = rpc('led')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	if status == '1':
		return 'on'
	else: 
		return 'off'

def serveLamp(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('lamp', up['on'])
	else:
		status = rpc('lamp')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	if status == '1':
		return 'up'
	else: 
		return 'down'
	

def serveFilt(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('filt', up['on'])
	else:
		status = rpc('filt')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	if status == '1':
		return 'on'
	else: 
		return 'off'
	
def serveFan(sreq):
	fan = rpc('fan')
	if fan is None:
		return ''
	return fan

def serveOutP(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('outP', up['on'])
	else:
		status = rpc('outP')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	if status == '1':
		return 'on'
	else: 
		return 'off'
	
def serveBrightness(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('brightness', up['on'])
	else:
		status = rpc('brightness')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	return status

def serveColor(sreq):
	up = fetchUriParams(sreq)
	if 'on' in up:
		status = rpc('color', up['on'])
	else:
		status = rpc('color')
	if status is None:
		return 'HTTP500: Internal server error\n'
		# return 'HTTP400: Bad request\n'
	return status

def serveWeb():
	cnn, addr = s_web.accept()
	print(f'Client connected from { str(addr) }')
	request = cnn.recv(1024)
	sreq = request.decode('utf-8')
	print(f'Request: { sreq[:indexOf(sreq,'\n')] }')

	if not sreq.startswith('GET '):
		cnn.send('HTTP400: Bad request\n')
		cnn.close()
		return

	sreq = sreq[4:indexOf(sreq,' ', 5)]

	if sreq.startswith('/?') or sreq.startswith('/index.htm'):
		payload = webpage()
	elif sreq.startswith('/led'):
		payload = serveLed(sreq)
	elif sreq.startswith('/filt'):
		payload = serveFilt(sreq)
	elif sreq.startswith('/fan'):
		payload = serveFan(sreq)
	elif sreq.startswith('/heat'):
		payload = serveHeat(sreq)
	elif sreq.startswith('/inP'):
		payload = serveInP(sreq)
	elif sreq.startswith('/outP'):
		payload = serveOutP(sreq)
	elif sreq.startswith('/temp'):
		payload = serveTemp(sreq)
	elif sreq.startswith('/brightness'):
		payload = serveBrightness(sreq)
	elif sreq.startswith('/color'):
		payload = serveColor(sreq)
	elif sreq.startswith('/lvl'):
		payload = serveLvl(sreq)
	elif sreq.startswith('/lamp'):
		payload = serveLamp(sreq)
	elif sreq == '/':
		payload = webpage()
	else:
		payload = 'HTTP404: Not found\n'
	print(f'Response: {payload.strip()[:200]}')
	cnn.send(payload)
	cnn.close()
# end def


def webpage():
	try:
		with open('index.html', 'r') as f:
			payload = f.read()
	except:
		payload = None

	if not payload:
		return 'HTTP404: Page not found\n'

	temp = rpc('temp')
	led = rpc('led')
	filt = rpc('filt')
	fan = rpc('fan')
	heat = rpc('heat')
	inP = rpc('inP')
	outP = rpc('outP')
	lvl = rpc('lvl')
	lamp = rpc('lamp')
	payload = payload.replace('<!--led-->', led, 1)
	payload = payload.replace('<!--temp-->', temp, 1)
	payload = payload.replace('<!--filt-->', filt, 1)
	payload = payload.replace('<!--fan-->', fan, 1)
	payload = payload.replace('<!--heat-->', heat, 1)
	payload = payload.replace('<!--inP-->', inP, 1)
	payload = payload.replace('<!--outP-->', outP, 1)
	payload = payload.replace('<!--lvl-->', lvl, 1)
	payload = payload.replace('<!--lamp-->', lamp, 1)
	return payload
# end def


def rpcTask( arg ):
	while True: # Forever
		utime.sleep(0.001)

		# 1. Read a line from the serial port
		with lkUART:
			line = uart.readline()
		if not line: continue
		line = line.decode('utf-8')
		line = line.strip()
		if not line or len(line) < 3: continue
		print(f'RP2040: {line}')

		# 2. Validate data
		# An rpc respose is:
		# id:functionName:result
		# fetch result and reqid = id:functionName
		scpos1 = indexOf(line, ':', 0)
		if scpos1 == -1: continue
		scpos2 = indexOf(line, ':', scpos1+1)
		if scpos2 == -1: continue

		# 3. Extract valid data: reqid and result
		reqid = line[:scpos2]
		result= line[scpos2+1:]

		# 4. Add data to the dictionary
		with lkRPCResponses:
			svRPCResponses[reqid] = result
			print(svRPCResponses)
# end def

def main():
	setup()

	# Start temperature retrieval task
	_thread.start_new_thread(rpcTask, [None] )
	# Main thread will serve web requests forever
	while True:
		serveWeb()
# end def

if __name__ == '__main__':
	try:
		main()
	except Exception as e:
		print('--- Caught Exception ---')
		import sys
		sys.print_exception(e)
		print('----------------------------')