import os
from machine import Pin, ADC, UART
from neopixel import NeoPixel
from utime import sleep_ms
import _thread
import ucollections

neoD = None
filt = None
fan = None
heater = None
inPump = None
outP = None

bobina1 = None
bobina2 = None
bobina3 = None
bobina4 = None

bobinas = None
dos_pasos = None

color = 360
brightness = 0.5

realizar= False #permite subir iluminacion

velocidad = 5 #ms
contador_pasos = 0 #cuenta del paso actual
cantidad_pasos = 3 #pasos totales para el modo de secuencia de 2 pasos
veces = 0 #total de pasos necesarios para 1 vuelta = 2048
ptotal = 0 # total de pasos para realizar 2 vueltas 4095
acabar = 1

# ## ##################################
# Shared vars and mutexes
# ## ##################################
uart    = None # Communication device with ESP32
lkUART  = _thread.allocate_lock()

adc     = None # ADC for reading temperature
lkADC   = _thread.allocate_lock()

adc1 = None
lkADC1 = _thread.allocate_lock()

adc2 = None
lkADC2 = _thread.allocate_lock()

adc3 = None
lkADC3 = _thread.allocate_lock()

rpcQ    = None   # Queue for received function calls
lkRPCQ  = _thread.allocate_lock()

svLedOn = False 
lkLedOn = _thread.allocate_lock()

svFiltOn = False 
lkFiltOn = _thread.allocate_lock()

svopOn = False  
lkopOn = _thread.allocate_lock()

svBrightnessOn = False  
lkBrightnessOn = _thread.allocate_lock()

svpColorOn = False
lkColorOn = _thread.allocate_lock()

svLampOn = False
lkLampOn = _thread.allocate_lock()

# ## ##################################
# Setup Functions
# ## ##################################
def setup():
	global  neoD, rpcQ, filt, fan, heater, inPump, outP, color, brightness, bobina1, bobina2, bobina3, bobina4, bobinas, dos_pasos
	setupADC()
	setupUART()
	neoD = NeoPixel(Pin(22),96)
	filt = Pin(23, Pin.OUT)
	fan = Pin(21, Pin.OUT)
	heater= Pin(19, Pin.OUT)
	inPump = Pin(15, Pin.OUT)
	outP = Pin(11, Pin.OUT)
	rpcQ = ucollections.deque((), 10)

	NL = 0
	while NL < 96:
		neoD[NL] = hsv2rgb(color, 1, 0) # set the first pixel to white
		neoD.write()              # write data to all pixels
		NL+=1		
	
	#Define los pines del Motor PaP
	bobina1 = Pin(20, Pin.OUT)
	bobina2 = Pin(18, Pin.OUT)
	bobina3 = Pin(10, Pin.OUT)
	bobina4 = Pin(9, Pin.OUT)
    
  	#Configura las GPIO como Salidas
	bobinas = list()
	bobinas.extend( [bobina1,bobina2,bobina3,bobina4] )
        
	#Secuencia a 2 pasos
	dos_pasos = ( int('1100',2),
			int('0110',2),
			int('0011',2),
			int('1001',2) )
    
# end def

def setupADC():
	global adc, adc2, adc3, adc1
	adc = ADC(4)
	adc2 = ADC(28)
	adc1 = ADC(27)        
	adc3 = ADC(29)       
	adc.read_u16()
	adc2.read_u16()
	adc1.read_u16()
	adc3.read_u16()
# end def

def setupUART():
	global uart
	pin_tx = Pin(0, Pin.OUT)
	pin_rx = Pin(1, Pin.IN)
	uart   = UART(0, baudrate=115200,
		tx=pin_tx, rx=pin_rx,
		timeout=1,
		timeout_char=1)
# end def

# ## ##################################
# Functions
# ## ##################################
def hsv2rgb(h, s, v):
	if (s < 0) or (v < 0) or (h > 360) or (s > 1) or (v > 1):
		return False
	C = s * v
	X = C * (1 - abs(h / 60.0 % 2 - 1))
	m = v - C
	if h < 60:
		R, G, B = C, X, 0
	elif h < 120:
		R, G, B = X, C, 0
	elif h < 180:
		R, G, B = 0, C, X
	elif h < 240:
		R, G, B = 0, X, C
	elif h < 300:
		R, G, B = X, 0, C
	else:
		R, G, B = C, 0, X
	return int((R + m) * 255), int((G + m) * 255), int((B + m) * 255)
	
	
def envia_pasos(paso, tipo, bobinas):
	bit = 1
	pasototal = 0
	while pasototal<4:
		if (tipo[paso]  & bit) == 0:
			bobinas[pasototal].off()
		else:
			bobinas[pasototal].on()
		bit = bit << 1
		pasototal +=1
	

def fetchRequests():
	s = None
	with lkUART:
		if not uart.any(): return
		try:
			s = uart.readline()
		except:
			return
	try:
		if s is None: return
		s = s.decode('utf-8')
		s = s.strip()
		if s is None or len(s) < 3: return
	except:
		return
	with lkRPCQ:
		rpcQ.append(s)
	print('ESP32: ', s, len(s), 'bytes')
# end def

def readTemp():
	aux = 0
	Sum=0
	while(aux<1000):
		x1 = adc1.read_u16()*3.3/65535      # Read ADC
		x3 = adc3.read_u16()*3.3 /65535      # Read ADC
		Vab= x3-x1
		Sum += Vab
		aux+=1
	Sum = Sum/1000
	temp=Sum/0.00047
	if (temp>=17):
		heater.off()
		fan.on()
	elif (temp<17):
		heater.on()
		fan.off()
	print(f'Temp: {temp} °C')
	return temp
# end def

def readLvl():
	lvl=adc2.read_u16()
	print(f'Level: {lvl}')
	return lvl

def returnRPC(i, f, retval):
	with lkUART:
		uart.write(f'{i}:{f}:{retval}\n')
	print(f'UART <= {i}:{f}:{retval}')
# end def

def onmotor():
	global veces, ptotal, contador_pasos, cantidad_pasos, acabar
	veces = 0 
	while veces <=acabar: #completar n vueltas

		if ptotal<=2048:
			envia_pasos(contador_pasos, dos_pasos, bobinas)
			contador_pasos += 1
			if contador_pasos > cantidad_pasos:
				contador_pasos = 0
                
		cantidad_pasos = 3
		sleep_ms(velocidad)
		ptotal += 1
            
		if ptotal == 2048: #completar 1 vuelta
			veces +=1	
			ptotal = 0
		
	
		
def offmotor():
	global veces, ptotal, contador_pasos, cantidad_pasos, acabar
	veces = 0 
	while veces <=acabar: #completar n vueltas

		if ptotal<=2048:
			envia_pasos(contador_pasos, dos_pasos, bobinas)
			contador_pasos -= 1
			if contador_pasos < 0:
				contador_pasos = cantidad_pasos
                
		cantidad_pasos = 3
		sleep_ms(velocidad)
		ptotal += 1
            
		if ptotal == 2048: #completar 1 vuelta
			veces +=1	
			ptotal = 0

def serveLed(i, f, p):
	global svLedOn
	try:
		if len(p) > 0:
			ledStat = int(p[0])
		else:
			ledStat = None
	except:
		ledStat = None
	with lkLedOn:
		if ledStat is not None:
			svLedOn = bool(ledStat)
			if svLedOn:
				NL = 0
				while NL < 96:
					neoD[NL] = hsv2rgb(color, 1, brightness) # set the first pixel to white
					neoD.write()              # write data to all pixels
					NL+=1	
			else:
				NL = 0
				while NL < 96:
					neoD[NL] = hsv2rgb(color, 1, 0) # set the first pixel to white
					neoD.write()              # write data to all pixels
					NL+=1		
		else:
			ledStat = svLedOn
	returnRPC(i, f, int(ledStat))
#end def
	
def serveLamp(i, f, p):
	global svLampOn, realizar
	try:
		if len(p) > 0:
			LampStat = int(p[0])
		else:
			LampStat = None
	except:
		LampStat = None
	with lkLampOn:
		if LampStat is not None:
			svLampOn = bool(LampStat)
			if svLampOn:
				if realizar:
					onmotor()
					realizar = False
			else:
				if realizar ==False:
					offmotor()
					realizar= True
		else:
			LampStat = svLampOn
	returnRPC(i, f, LampStat)

def serveFilt(i, f, p):
	global svFiltOn
	try:
		if len(p) > 0:
			FiltStat = int(p[0])
		else:
			FiltStat = None
	except:
		FiltStat = None
	with lkFiltOn:
		if FiltStat is not None:
			svFiltOn = bool(FiltStat)
			if svFiltOn:
				filt.on()
			else:
				filt.off()
		else:
			FiltStat = svFiltOn
	returnRPC(i, f, int(FiltStat))

def serveOutP(i, f, p):
	global svopOn
	try:
		if len(p) > 0:
			opStat = int(p[0])
		else:
			opStat = None
	except:
		opStat = None
	with lkopOn:
		if opStat is not None:
			svopOn = bool(opStat)
			if svopOn:
				outP.on()
			else:
				outP.off()
		else:
			opStat = svopOn
	returnRPC(i, f, int(opStat))
	
def serveBrightness(i, f, p):
	global svBrightnessOn, brightness, color
	try:
		if len(p) > 0:
			brightnessStat = int(p[0])
		else:
			brightnessStat = None
	except:
		brightnessStat = None
	with lkBrightnessOn:
		if brightnessStat is not None:
			if brightnessStat>100: brightnessStat=100
			elif brightnessStat<0: brightnessStat=0
			brightness = brightnessStat/100
			NL = 0
			while NL < 96:
				neoD[NL] = hsv2rgb(color, 1, brightness) # set the first pixel to white
				neoD.write()              # write data to all pixels
				NL+=1
		else:
			brightnessStat = svBrightnessOn
	returnRPC(i, f, brightnessStat)

def serveColor(i,f,p):
	global svColorOn, color, brightness
	try:
		if len(p) > 0:
			colorStat = int(p[0])
		else:
			colorStat = None
	except:
		colorStat = None
	with lkColorOn:
		if colorStat is not None:
			if colorStat>360: colorStat=360
			elif colorStat<0: colorStat=0
			color = colorStat
			NL = 0
			while NL < 96:
				neoD[NL] = hsv2rgb(color, 1, brightness) # set the first pixel to white
				neoD.write()              # write data to all pixels
				NL+=1
		else:
			colorStat = svColorOn
	returnRPC(i, f, colorStat)

def serveNot(s):
	with lkUART:
		uart.write(f'{s}:-1\n')
#end def

def serveFan(i, f, p):
	fanStat = fan.value()
	if bool(fanStat):
		returnRPC(i, f, 'on')
	else:
		returnRPC(i, f, 'off')
		
	

def serveInP(i, f, p):
	ipStat = inPump.value()
	if bool(ipStat):
		returnRPC(i, f, 'on')
	else:
		returnRPC(i, f, 'off')

def serveHeat(i, f, p):
	heatStat = heater.value()
	if bool(heatStat):
		returnRPC(i, f, 'on')
	else:
		returnRPC(i, f, 'off')

def serveTemp(i, f, p):
	temp = readTemp()
	returnRPC(i, f, temp)
# end def

def serveLvl(i,f,p):
	lvl = readLvl()
	print('Nivel: {}'.format(lvl))
	outpStat = outP.value()
	if 32000<lvl:
		state = "Tank over half full"
		if bool(outpStat):
			inPump.off()
		else:
			inPump.off()
	else:
		state = "Tank less than a half full"
		if bool(outpStat):
			inPump.off()
		else:
			inPump.on()
	returnRPC(i,f,state)

def serveRPC(s):
	i, f, p = splitRPC(s)
	if f == 'temp':
		serveTemp(i, f, p)
	elif f == 'led':
		serveLed(i, f, p)
	elif f == 'filt':
		serveFilt(i,f,p)
	elif f == 'fan':
		serveFan(i,f,p)
	elif f == 'heat':
		serveHeat(i,f,p)
	elif f == 'inP':
		serveInP(i,f,p)
	elif f == 'outP':
		serveOutP(i,f,p)
	elif f=='brightness':
		serveBrightness(i,f,p)
	elif f=='color':
		serveColor(i,f,p)
	elif f == 'lvl':
		serveLvl(i,f,p)
	elif f == 'lamp':
		serveLamp(i,f,p)
	else:
		serveNot(s)
#end def


def splitRPC(s):
	parts = s.split(':', 3)
	if len(parts) < 2:
		return None, None, None
	elif len(parts) < 3:
		parts.append('')
	i = parts[0]
	f = parts[1]
	p = parts[2].split(',')
	return i, f, p
# end def


def core1Task(arg):
	print('Core1 task: Running')
	while True:
		# 1. Retrieve requests from UART
		fetchRequests()

		# 2. Lock Q. If there is a request,
		# dequeue it and serve it.
		s = None
		with lkRPCQ:
			if len(rpcQ) > 0:
				s = rpcQ.popleft()
		if s is not None:
			print(f'Core1: Dispatch: «{s}»')
			serveRPC(s)
		# If there are no requests,
		# go idle for 1ms
		# utime.sleep(0.001)
#end def


# ## ##################################
# Main
# ## ##################################
def main():
	setup()

	# Start Core1 task:
	_thread.start_new_thread(core1Task, [None] )

	# Main thread (Core0) will serve RPC requests forever
	while True:
		# 1. Retrieve requests from UART
		fetchRequests()

		# 2. Lock Q. If there is a request,
		# dequeue it and serve it.
		s = None
		with lkRPCQ:
			if len(rpcQ) > 0:
				s = rpcQ.popleft()
		if s is not None:
			print(f'Core0: Dispatch «{s}»')
			serveRPC(s)

		# s = input('?: ')
		# with lkRPCQ:
		# 	rpcQ.append(s)
# end def


# ## ##################################
# Anchor
# ## ##################################
if __name__ == '__main__':
	try:
		main()
	except Exception as e:
		print('--- Caught Exception ---')
		import sys
		sys.print_exception(e)
		print('----------------------------')


