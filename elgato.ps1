<#
.SYNOPSIS
	Control Elgato Key Lights from Windows PowerShell (no Python required).

.DESCRIPTION
	Mirrors the Python CLI:
		find | list | toggle | on | off | status | info | brighter | dimmer | warmer | cooler | set
	Lights can be targeted by:
		- number from `list`
		- IP or IP:PORT
	Persists a config file at:
		$env:APPDATA\ElgatoControl\elgato.control.json

.NOTES
	Default port if omitted: 9123
	Temp format: Elgato “temperature” (143–344) or Kelvin 2900–7000 (increments of 50)
#>

[CmdletBinding()]
param(
	[Parameter(Mandatory=$true, Position=0)]
	[ValidateSet('find','list','toggle','on','off','status','info','brighter','dimmer','warmer','cooler','set')]
	[string]$Command,

	# Repeatable: -Light 1  or  -Light 192.168.1.50  or  -Light 192.168.1.50:9123
	[string[]]$Light,

	# For `set`: -On / -Off are mutually exclusive (or use -o On|Off style via -On/-Off flags)
	[switch]$On,
	[switch]$Off,

	# For `set`: -Brightness 3..100 (integer or "50%")
	[string]$Brightness,

	# For `set`: -Temperature accepts Kelvin (e.g. 3400 or "3400k"); will be converted to Elgato value.
	[string]$Temperature
)

Set-PSDebug -Trace 0

# ------------------------ Constants & Config ------------------------
$AppName    = 'ElgatoControl'
$AppAuthor  = 'AaronDCampbell'
$DefaultPort = 9123
$ConfigDir  = Join-Path $env:LOCALAPPDATA $AppAuthor $AppName
$ConfigPath = Join-Path $ConfigDir 'elgato.control.json'

# ------------------------ Helpers ------------------------
function Ensure-ConfigDir {
	if (-not (Test-Path $ConfigDir)) {
		New-Item -Path $ConfigDir -ItemType Directory | Out-Null
	}
}

function ConvertTo-ElgatoTemp {
	param([int]$Kelvin)
	# Elgato temp = round(1,000,000 / K)
	[int][math]::Round(1000000.0 / $Kelvin)
}
function ConvertFrom-ElgatoTemp {
	param([int]$ElgatoTemp)
	# Kelvin ≈ round to nearest 50: 50 * round((1,000,000 / temp) / 50)
	$k = 1000000.0 / $ElgatoTemp
	50 * [math]::Round($k / 50.0)
}

function Normalize-Brightness {
	param([Parameter(Mandatory)]$Value)
	# Accept "50" or "50%"
	if ($Value -is [int]) { return [int]$Value }
	$s = "$Value"
	if ($s.EndsWith('%')) { $s = $s.Substring(0, $s.Length-1) }
	if (-not [int]::TryParse($s, [ref]([int]$null))) {
		throw "Invalid brightness: $Value (expected 3-100)"
	}
	[int]$s
}
function Test-Brightness {
	param([int]$Value)
	return ($Value -ge 3 -and $Value -le 100)
}

function Normalize-TemperatureKelvin {
	param([Parameter(Mandatory)]$Value)
	# Accept "3400" or "3400k"
	if ($Value -is [int]) { $k=[int]$Value } else {
		$s = "$Value"
		if ($s.ToLower().EndsWith('k')) { $s = $s.Substring(0, $s.Length-1) }
		if (-not [int]::TryParse($s, [ref]([int]$null))) {
			throw "Invalid temperature: $Value (expected Kelvin 2900–7000 in steps of 50)"
		}
		$k = [int]$s
	}
	if ($k -lt 2900 -or $k -gt 7000 -or $k % 50 -ne 0) {
		throw "Invalid temperature: $k (valid Kelvin is 2900–7000 in increments of 50)"
	}
	return $k
}

function OnOff-ToBool {
	param($v)
	if ($v -is [bool]) { return [bool]$v }
	$s = "$v"
	return ($s -eq '1' -or $s.ToLower() -eq 'on' -or $s.ToLower() -eq 'true')
}

function Invoke-ElgatoGet {
	param([string]$Location, [string]$Path)
	$url = "http://$Location$Path"
	Invoke-RestMethod -Method GET -Uri $url -TimeoutSec 3
}
function Invoke-ElgatoPut {
	param([string]$Location, [string]$Path, [hashtable]$Body)
	$url = "http://$Location$Path"
	$json = $Body | ConvertTo-Json -Depth 6
	Invoke-RestMethod -Method PUT -Uri $url -TimeoutSec 3 -Body $json -ContentType 'application/json'
}

function Get-ConfigLights {
	if (Test-Path $ConfigPath) {
		try {
			(Get-Content $ConfigPath -Raw | ConvertFrom-Json -AsHashtable)
		} catch { @() }
	} else { @() }
}
function Save-ConfigLights {
	param([array]$Lights)
	Ensure-ConfigDir
	$Lights | ConvertTo-Json -Depth 6 | Set-Content -Path $ConfigPath -Encoding UTF8
}

function Parse-LightString {
	param([string]$s)
	if ($s -match ':') {
		$ip, $port = $s.Split(':',2)
	} else {
		$ip = $s
		$port = ''
	}
	# Validate IP
	[void][System.Net.IPAddress]::Parse($ip)
	if (-not $port) { $port = $DefaultPort }
	if (-not [int]::TryParse($port, [ref]([int]$null))) {
		throw "Invalid port for light: $s"
	}
	return @{
		name = $s
		light = "$ip`:$port"
	}
}

function Resolve-RequestedLights {
	param([string[]]$Requested)
	$lights = @()

	if ($Requested -and $Requested.Count -gt 0) {
		# Need config to support numeric selection
		$config = Get-ConfigLights

		foreach ($item in $Requested) {
			if ([int]::TryParse($item, [ref]([int]$null))) {
				$idx = [int]$item
				if ($idx -le 0 -or $idx -gt $config.Count) {
					throw "Invalid light number: $item"
				}
				$lights += $config[$idx-1]
			} else {
				# IP[:PORT]
				$lights += (Parse-LightString -s $item)
			}
		}
		return ,$lights
	}

	# If nothing requested, fallback to config; else try discovery
	$config2 = Get-ConfigLights
	if ($config2 -and $config2.Count -gt 0) { return ,$config2 }

	# No config saved—try discovery
	return ,(Find-Lights -NonInteractive)
}

function Get-LightStatus {
	param([hashtable]$Light)
	$res = Invoke-ElgatoGet -Location $Light.light -Path '/elgato/lights'
	$res.lights[0]
}
function Get-LightInfo {
	param([hashtable]$Light)
	Invoke-ElgatoGet -Location $Light.light -Path '/elgato/accessory-info'
}

function Set-LightStatus {
	param(
		[hashtable]$Light,
		$On = $null,
		$Brightness = $null,
		$Temperature = $null
	)
	$payload = @{}
	if ($null -ne $On) {
		$payload.on = if (OnOff-ToBool $On) { 1 } else { 0 }
	}
	if ($null -ne $Brightness) {
		$b = Normalize-Brightness $Brightness
		if (-not (Test-Brightness $b)) { throw "Brightness must be 3–100" }
		$payload.brightness = $b
	}
	if ($null -ne $Temperature) {
		# Accept Kelvin or raw 143–344
		$t = "$Temperature"
		if ($t.ToLower().EndsWith('k') -or [int]::TryParse($t,[ref]([int]$null)) -and [int]$t -ge 2900) {
			$k = Normalize-TemperatureKelvin $Temperature
			$payload.temperature = ConvertTo-ElgatoTemp $k
		} else {
			# raw
			$raw = [int]$t
			if ($raw -lt 143 -or $raw -gt 344) { throw "Raw temperature must be 143–344" }
			$payload.temperature = $raw
		}
	}
	if ($payload.Keys.Count -eq 0) { throw "Nothing to set. Use -On/-Off, -Brightness, and/or -Temperature." }

	$body = @{
		numberOfLights = 1
		lights         = @($payload)
	}
	[void](Invoke-ElgatoPut -Location $Light.light -Path '/elgato/lights' -Body $body)
	return $true
}

# Discovery for Windows (no Bonjour):
# 1) Take neighbors from ARP/ND caches
# 2) Try http://IP:9123/elgato/accessory-info and detect displayName
function Get-CandidateIPs {
	$ips = @()

	try {
		# Windows 10/11: Get-NetNeighbor
		$ips += (Get-NetNeighbor -ErrorAction SilentlyContinue | Where-Object {$_.State -match 'Reachable|Stale|Delay|Probe'} | Select-Object -ExpandProperty IPAddress)
	} catch {}

	try {
		# Fallback: arp -a
		$arp = arp -a 2>$null
		foreach ($line in $arp) {
			if ($line -match '^\s*([\d\.]+)\s') { $ips += $matches[1] }
		}
	} catch {}

	$ips | Sort-Object -Unique
}

function Try-ProbeLight {
	param([string]$IP, [int]$Port = $DefaultPort)
	try {
		$info = Invoke-ElgatoGet -Location "$IP`:$Port" -Path '/elgato/accessory-info'
		if ($info.displayName) {
			return @{
				name  = [string]$info.displayName
				light = "$IP`:$Port"
			}
		}
	} catch {}
	return $null
}

function Find-Lights {
	param([switch]$NonInteractive)
	Write-Host "Finding Lights..."
	$found = @()

	# Probe known neighbors at default port
	foreach ($ip in Get-CandidateIPs) {
		$obj = Try-ProbeLight -IP $ip -Port $DefaultPort
		if ($obj) {
			$found += $obj
			Write-Host "$($obj.name) found at $($obj.light)"
		}
	}

	if (-not $NonInteractive) {
		Write-Host "Found $($found.Count) lights."
	}

	if ($found.Count -gt 0) {
		Save-ConfigLights -Lights $found
	}
	return ,$found
}

# ------------------------ Commands ------------------------
function Do-List {
	param([hashtable[]]$Lights)
	$i = 1
	foreach ($l in $Lights) {
		"{0}. {1} ({2})" -f $i, $l.name, $l.light
		$i++
	}
}

function Do-Status {
	param([hashtable[]]$Lights)
	foreach ($l in $Lights) {
		$st = Get-LightStatus -Light $l
		$friendly = [ordered]@{
			on          = ($(if ($st.on -eq 1) {'on'} else {'off'}))
			brightness  = ("{0}%" -f $st.brightness)
			temperature = ("{0}K" -f (ConvertFrom-ElgatoTemp $st.temperature))
		}
		Write-Host "Status for $($l.name):"
		($friendly | ConvertTo-Json -Depth 5)
	}
}

function Do-Info {
	param([hashtable[]]$Lights)
	foreach ($l in $Lights) {
		$info = Get-LightInfo -Light $l
		Write-Host "Info for $($l.name):"
		($info | ConvertTo-Json -Depth 8)
	}
}

function Do-Toggle {
	param([hashtable[]]$Lights)
	foreach ($l in $Lights) {
		$on = (Get-LightStatus -Light $l).on
		[void](Set-LightStatus -Light $l -On:($on -eq 0))
	}
}

function Do-OnOff {
	param([hashtable[]]$Lights, [bool]$OnState)
	foreach ($l in $Lights) {
		[void](Set-LightStatus -Light $l -On:$OnState)
	}
}

function Do-BrightnessDelta {
	param([hashtable[]]$Lights, [int]$Delta)
	foreach ($l in $Lights) {
		$cur = (Get-LightStatus -Light $l).brightness
		$new = [math]::Max(3, [math]::Min(100, $cur + $Delta))
		[void](Set-LightStatus -Light $l -Brightness $new)
	}
}

function Do-TemperatureDelta {
	param([hashtable[]]$Lights, [int]$DeltaRaw)
	foreach ($l in $Lights) {
		$cur = (Get-LightStatus -Light $l).temperature
		$new = [math]::Max(143, [math]::Min(344, $cur + $DeltaRaw))
		[void](Set-LightStatus -Light $l -Temperature $new)
	}
}

function Do-Set {
	param([hashtable[]]$Lights, $OnParam, $BrightnessParam, $TemperatureParam)
	foreach ($l in $Lights) {
		[void](Set-LightStatus -Light $l -On:$OnParam -Brightness:$BrightnessParam -Temperature:$TemperatureParam)
	}
}

# ------------------------ Dispatch ------------------------
try {
	switch ($Command) {
		'find'     { [void](Find-Lights) }
		'list'     { $ls = Resolve-RequestedLights -Requested $Light; Do-List $ls }
		'toggle'   { $ls = Resolve-RequestedLights -Requested $Light; Do-Toggle $ls }
		'on'       { $ls = Resolve-RequestedLights -Requested $Light; Do-OnOff $ls $true }
		'off'      { $ls = Resolve-RequestedLights -Requested $Light; Do-OnOff $ls $false }
		'status'   { $ls = Resolve-RequestedLights -Requested $Light; Do-Status $ls }
		'info'     { $ls = Resolve-RequestedLights -Requested $Light; Do-Info $ls }
		'brighter' { $ls = Resolve-RequestedLights -Requested $Light; Do-BrightnessDelta $ls 5 }
		'dimmer'   { $ls = Resolve-RequestedLights -Requested $Light; Do-BrightnessDelta $ls -5 }
		'warmer'   { $ls = Resolve-RequestedLights -Requested $Light; Do-TemperatureDelta $ls 5 }
		'cooler'   { $ls = Resolve-RequestedLights -Requested $Light; Do-TemperatureDelta $ls -5 }
		'set' {
			$onParam = $null
			if ($On -and $Off) { throw "Use only one of -On or -Off." }
			elseif ($On) { $onParam = $true }
			elseif ($Off) { $onParam = $false }

			$bParam = $null
			if ($PSBoundParameters.ContainsKey('Brightness')) { $bParam = $Brightness }

			$tParam = $null
			if ($PSBoundParameters.ContainsKey('Temperature')) { $tParam = $Temperature }

			$ls = Resolve-RequestedLights -Requested $Light
			Do-Set -Lights $ls -OnParam $onParam -BrightnessParam $bParam -TemperatureParam $tParam
		}
	}
} catch {
	Write-Error $_.Exception.Message
	exit 1
}
