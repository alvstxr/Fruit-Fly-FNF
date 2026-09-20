import sys.io.File;

var SENSE_TICK = 0.016;
var PRESS_TICK = 0.016;
var IDLE_TICK = 0.5;
var SPAWN_GAP = 2.0;

var down = [false, false, false, false];
var tap = [false, false, false, false];
var rel = [false, false, false, false];
var wanted = [false, false, false, false];
var prev = [false, false, false, false];
var bits = [false, false, false, false];
var etas = [null, null, null, null];
var due = [false, false, false, false];
var sustain = [false, false, false, false];
var holdUntil = [0.0, 0.0, 0.0, 0.0];

var senseClock = 0.0;
var pressClock = 0.0;
var spawnClock = 99.0;
var idleWrite = 0.0;
var brainAlive = false;
var spawned = false;
var seq = 0;
var rating = "";
var lastCombo = 0;
var lastPress = "";
var isWin = false;
var sensePath = "";
var pressPath = "";
var localSense = "mods/fruit-fly/python/fly_fnf_sense.txt";
var boundLine = null;
var relaxed = false;
var scanPos = 0.0;
var scanLine = null;
var pending = [null, null, null, null];

function new() {
	isWin = detectWindows();
	var dir = tmpDir();
	sensePath = dir + "/fly_fnf_sense.txt";
	pressPath = dir + "/fly_fnf_press.txt";
}

function preUpdate(elapsed:Float) {
	var dt = elapsed;
	if (dt == null || dt <= 0 || dt > 1)
		dt = 0.016;
	senseClock = senseClock + dt;
	pressClock = pressClock + dt;
	spawnClock = spawnClock + dt;
	if (!relaxed) {
		relaxed = true;
		try {
			if (FlxG.autoPause)
				FlxG.autoPause = false;
		} catch (e:Dynamic) {}
	}

	if (pressClock >= PRESS_TICK) {
		pressClock = 0;
		readPress();
	}

	var line = livePlayerLine();
	if (line == null) {
		if (boundLine != null)
			unbind();
		lastCombo = 0;
		clearWanted();
		edges();
		idleWrite = idleWrite + dt;
		if (idleWrite >= IDLE_TICK) {
			idleWrite = 0;
			clearLanes();
			writeSense(false, 0, 0);
		}
		return;
	}
	idleWrite = 0;

	try {
		if (line.cpu)
			line.cpu = false;
	} catch (e:Dynamic) {}
	if (brainAlive) {
		if (boundLine != line)
			bind(line);
	} else if (boundLine != null) {
		unbind();
	}

	if (!brainAlive && !spawned)
		trySpawn();

	var pos = 0.0;
	try {
		pos = Conductor.songPosition;
	} catch (e:Dynamic) {}
	scan(line, pos);
	syncWanted();
	edges();
	if (brainAlive)
		flushHits();

	if (senseClock >= SENSE_TICK) {
		senseClock = 0;
		var combo = 0;
		try {
			combo = PlayState.instance.combo;
		} catch (e:Dynamic) {}
		if (combo > lastCombo)
			rating = "good";
		else if (combo < lastCombo)
			rating = "miss";
		lastCombo = combo;
		writeSense(true, pos, combo);
	}
}

function destroy() {
	unbind();
	clearLanes();
	writeSense(false, 0, 0);
}

function livePlayerLine() {
	var state = null;
	try {
		state = PlayState.instance;
	} catch (e:Dynamic) {
		return null;
	}
	if (state == null)
		return null;
	try {
		if (state.paused || state.inCutscene)
			return null;
	} catch (e:Dynamic) {}
	var found = null;
	try {
		for (line in state.strumLines.members) {
			if (line != null && !line.opponentSide)
				found = line;
		}
	} catch (e:Dynamic) {}
	if (found != null)
		return found;
	try {
		for (line in state.strumLines.members) {
			if (line != null && !line.cpu)
				found = line;
		}
	} catch (e:Dynamic) {}
	if (found != null)
		return found;
	try {
		if (state.playerStrums != null)
			return state.playerStrums;
	} catch (e:Dynamic) {}
	return null;
}

function bind(line) {
	boundLine = line;
	if (line == null)
		return;
	try {
		if (line.cpu)
			line.cpu = false;
	} catch (e:Dynamic) {}
	if (line.members == null)
		return;
	var n = 0;
	try {
		n = line.members.length;
	} catch (e:Dynamic) {
		return;
	}
	if (n > 0) {
		line.members[0].getPressed = function(_s) return down[0];
		line.members[0].getJustPressed = function(_s) return tap[0];
		line.members[0].getJustReleased = function(_s) return rel[0];
	}
	if (n > 1) {
		line.members[1].getPressed = function(_s) return down[1];
		line.members[1].getJustPressed = function(_s) return tap[1];
		line.members[1].getJustReleased = function(_s) return rel[1];
	}
	if (n > 2) {
		line.members[2].getPressed = function(_s) return down[2];
		line.members[2].getJustPressed = function(_s) return tap[2];
		line.members[2].getJustReleased = function(_s) return rel[2];
	}
	if (n > 3) {
		line.members[3].getPressed = function(_s) return down[3];
		line.members[3].getJustPressed = function(_s) return tap[3];
		line.members[3].getJustReleased = function(_s) return rel[3];
	}
}

function unbind() {
	var line = boundLine;
	boundLine = null;
	if (line == null || line.members == null)
		return;
	var n = 0;
	try {
		n = line.members.length;
	} catch (e:Dynamic) {
		return;
	}
	var i = 0;
	while (i < n && i < 4) {
		try {
			line.members[i].getPressed = null;
			line.members[i].getJustPressed = null;
			line.members[i].getJustReleased = null;
		} catch (e:Dynamic) {}
		i = i + 1;
	}
}

function clearLanes() {
	etas[0] = null;
	etas[1] = null;
	etas[2] = null;
	etas[3] = null;
	due[0] = false;
	due[1] = false;
	due[2] = false;
	due[3] = false;
	sustain[0] = false;
	sustain[1] = false;
	sustain[2] = false;
	sustain[3] = false;
	holdUntil[0] = 0;
	holdUntil[1] = 0;
	holdUntil[2] = 0;
	holdUntil[3] = 0;
}

function clearWanted() {
	wanted[0] = false;
	wanted[1] = false;
	wanted[2] = false;
	wanted[3] = false;
	bits[0] = false;
	bits[1] = false;
	bits[2] = false;
	bits[3] = false;
}

function edges() {
	var i = 0;
	while (i < 4) {
		var next = wanted[i] == true;
		tap[i] = next && !prev[i];
		rel[i] = !next && prev[i];
		down[i] = next;
		prev[i] = next;
		i = i + 1;
	}
}

function syncWanted() {
	if (!brainAlive) {
		clearWanted();
		return;
	}
	wanted[0] = bits[0];
	wanted[1] = bits[1];
	wanted[2] = bits[2];
	wanted[3] = bits[3];
}

function takeNote(note) {
	if (note == null)
		return;
	if (note.alive == false)
		return;
	var lane = note.noteData;
	if (lane == null)
		return;
	lane = Std.int(lane);
	if (lane < 0)
		lane = -lane;
	lane = lane % 4;
	var t = note.strumTime;
	var sus = note.isSustainNote == true;
	var hit = note.wasGoodHit == true;
	if (note.avoid == true)
		return;
	var diff = t - scanPos;
	if (sus) {
		if (diff <= 50 && diff >= -220) {
			sustain[lane] = true;
			if (holdUntil[lane] < t + 80)
				holdUntil[lane] = t + 80;
		}
		if (brainAlive && bits[lane] && !hit && diff <= 40 && diff >= -90)
			pending[lane] = note;
		return;
	}
	if (hit)
		return;
	if (diff > -80 && diff < 180) {
		if (etas[lane] == null || Math.abs(diff) < Math.abs(etas[lane] * 1000))
			etas[lane] = diff * 0.001;
	}
	if (diff <= 32 && diff >= -28) {
		due[lane] = true;
		if (brainAlive && bits[lane] && diff <= 46 && diff >= -40)
			pending[lane] = note;
	}
	var slen = note.sustainLength;
	if (slen != null && slen > 80 && scanPos >= t - 32 && scanPos <= t + slen + 40) {
		sustain[lane] = true;
		holdUntil[lane] = t + slen;
	}
}

function scan(line, songPos:Float) {
	etas[0] = null;
	etas[1] = null;
	etas[2] = null;
	etas[3] = null;
	due[0] = false;
	due[1] = false;
	due[2] = false;
	due[3] = false;
	sustain[0] = false;
	sustain[1] = false;
	sustain[2] = false;
	sustain[3] = false;
	scanPos = songPos;
	scanLine = line;
	pending[0] = null;
	pending[1] = null;
	pending[2] = null;
	pending[3] = null;
	var used = false;
	try {
		line.notes.forEach(takeNote);
		used = true;
	} catch (e:Dynamic) {}
	if (!used) {
		var notes = null;
		try {
			notes = line.notes.members;
		} catch (e:Dynamic) {
			return;
		}
		if (notes == null)
			return;
		var count = notes.length;
		var seen = 0;
		var i = 0;
		while (i < count && seen < 64) {
			var note = notes[i];
			i = i + 1;
			if (note == null)
				continue;
			if (note.strumTime > songPos + 180)
				continue;
			if (note.strumTime < songPos - 220)
				break;
			if (note.alive == false)
				continue;
			takeNote(note);
			seen = seen + 1;
		}
	}
	var ch = 0;
	while (ch < 4) {
		if (songPos < holdUntil[ch])
			sustain[ch] = true;
		else
			holdUntil[ch] = 0;
		ch = ch + 1;
	}
}

function flushHits() {
	var k = 0;
	while (k < 4) {
		var note = pending[k];
		pending[k] = null;
		if (note != null && scanLine != null && bits[k]) {
			try {
				PlayState.instance.goodNoteHit(scanLine, note);
			} catch (e:Dynamic) {}
		}
		k = k + 1;
	}
}

function writeSense(song:Bool, songPos:Float, combo:Int) {
	seq = seq + 1;
	var text = "v=1 song=" + (song ? "1" : "0") + " t=" + songPos + " combo=" + combo + " seq=" + seq + " keys=0 layout=wasd_arrows\n";
	text = text + "e=" + num(etas[0]) + "," + num(etas[1]) + "," + num(etas[2]) + "," + num(etas[3]) + "\n";
	text = text + "s=" + (sustain[0] ? "1" : "0") + "," + (sustain[1] ? "1" : "0") + "," + (sustain[2] ? "1" : "0") + "," + (sustain[3] ? "1" : "0") + "\n";
	text = text + "d=" + (due[0] ? "1" : "0") + "," + (due[1] ? "1" : "0") + "," + (due[2] ? "1" : "0") + "," + (due[3] ? "1" : "0") + "\n";
	if (rating != "") {
		text = text + "r=" + rating + "\n";
		rating = "";
	}
	try {
		File.saveContent(sensePath, text);
	} catch (e:Dynamic) {}
	try {
		File.saveContent(localSense, text);
	} catch (e:Dynamic) {}
}

function readPress() {
	var text = null;
	try {
		text = File.getContent(pressPath);
	} catch (e:Dynamic) {}
	if (text == null || text.length < 3) {
		try {
			text = File.getContent("mods/fruit-fly/python/fly_fnf_press.txt");
		} catch (e:Dynamic) {}
	}
	if (text == null || text.length < 3)
		return;
	if (text == lastPress)
		return;
	lastPress = text;
	var live = false;
	var quit = false;
	var next = [false, false, false, false];
	var parts = text.split(" ");
	var i = 0;
	while (i < parts.length) {
		var part = parts[i];
		i = i + 1;
		if (part.indexOf("alive=") == 0)
			live = part.substr(6) != "0";
		else if (part.indexOf("quit=") == 0)
			quit = part.substr(5) != "0";
		else if (part.indexOf("m=") == 0) {
			var m = part.substr(2).split(",");
			var k = 0;
			while (k < 4 && k < m.length) {
				next[k] = m[k] == "1";
				k = k + 1;
			}
		}
	}
	if (quit) {
		brainAlive = false;
		clearWanted();
		return;
	}
	brainAlive = live;
	if (live) {
		bits[0] = next[0];
		bits[1] = next[1];
		bits[2] = next[2];
		bits[3] = next[3];
	} else {
		bits[0] = false;
		bits[1] = false;
		bits[2] = false;
		bits[3] = false;
	}
}

function trySpawn() {
	if (brainAlive || spawned)
		return;
	if (spawnClock < SPAWN_GAP)
		return;
	spawnClock = 0;
	spawned = true;
	var path = launcherPath();
	if (path == null || path == "")
		return;
	var abs = makeAbs(path);
	if (!isWin) {
		try {
			var p = new sys.io.Process("/bin/sh", [path, "--detach"]);
			try {
				p.close();
			} catch (e2:Dynamic) {}
		} catch (e:Dynamic) {}
		return;
	}
	try {
		var p = new sys.io.Process("cmd.exe", ["/c", "start", "FlyBrainWin", "/b", abs]);
		try {
			p.close();
		} catch (e2:Dynamic) {}
	} catch (e:Dynamic) {}
}

function makeAbs(path:String) {
	if (path != null && path.indexOf(":") >= 0)
		return path.split("/").join("\\");
	var cwd = "";
	try {
		cwd = Sys.getCwd();
	} catch (e:Dynamic) {}
	if (cwd == null)
		cwd = "";
	if (cwd != "") {
		var last = cwd.substr(cwd.length - 1);
		if (last != "/" && last != "\\")
			cwd = cwd + "/";
	}
	return (cwd + path).split("/").join("\\");
}

function launcherPath() {
	var name = isWin ? "fly_brain.bat" : "fly_brain.sh";
	var roots = ["mods/fruit-fly/python/", "./mods/fruit-fly/python/", "addons/fruit-fly/python/"];
	var i = 0;
	while (i < roots.length) {
		var candidate = roots[i] + name;
		i = i + 1;
		try {
			if (sys.FileSystem.exists(candidate))
				return candidate;
		} catch (e:Dynamic) {}
	}
	return null;
}

function detectWindows() {
	try {
		if (Sys.getEnv("OS") == "Windows_NT")
			return true;
	} catch (e:Dynamic) {}
	return false;
}

function tmpDir() {
	if (isWin) {
		try {
			var t = Sys.getEnv("TEMP");
			if (t == null || t == "")
				t = Sys.getEnv("TMP");
			if (t != null && t != "")
				return t;
		} catch (e:Dynamic) {}
		return ".";
	}
	return "/tmp";
}

function num(v) {
	if (v == null)
		return "";
	return Std.string(v);
}
