import sys.io.File;
import sys.FileSystem;

var SENSE_TICK = 0.008;
var PRESS_TICK = 0.008;
var IDLE_TICK = 0.25;
var SPAWN_GAP = 4.0;
var STALE = 1.5;

var down = [false, false, false, false];
var tap = [false, false, false, false];
var rel = [false, false, false, false];
var wanted = [false, false, false, false];
var prev = [false, false, false, false];
var etas = [null, null, null, null];
var due = [false, false, false, false];
var sustain = [false, false, false, false];

var senseClock = 0.0;
var pressClock = 0.0;
var spawnClock = 99.0;
var brainAlive = false;
var seq = 0;
var rating = "";
var lastCombo = 0;
var isWin = false;
var sensePath = "";
var pressPath = "";
var boundLine = null;

function new() {
	isWin = detectWindows();
	var dir = tmpDir();
	sensePath = dir + "/fly_fnf_sense.txt";
	pressPath = dir + "/fly_fnf_press.txt";
	relax();
	readPress();
	trySpawn();
}

function preUpdate(elapsed:Float) {
	var dt = elapsed;
	if (dt == null || dt <= 0 || dt > 1)
		dt = 0.016;
	senseClock = senseClock + dt;
	pressClock = pressClock + dt;
	spawnClock = spawnClock + dt;
	relax();

	if (pressClock >= PRESS_TICK) {
		pressClock = 0;
		readPress();
		edges();
	}

	var line = livePlayerLine();
	if (line == null) {
		lastCombo = 0;
		clearWanted();
		edges();
		if (senseClock >= IDLE_TICK) {
			senseClock = 0;
			clearLanes();
			writeSense(false, 0, 0);
		}
		trySpawn();
		return;
	}

	if (line.cpu)
		line.cpu = false;
	if (!brainAlive)
		trySpawn();

	if (senseClock >= SENSE_TICK) {
		senseClock = 0;
		var pos = Conductor.songPosition;
		var combo = comboCount();
		judge(combo);
		scan(line, pos);
		writeSense(true, pos, combo);
	}
}

function destroy() {
	clearLanes();
	writeSense(false, 0, 0);
}

function relax() {
	if (FlxG.autoPause)
		FlxG.autoPause = false;
}

function livePlayerLine() {
	var state = PlayState.instance;
	if (state == null)
		return null;
	try {
		if (state.paused || state.inCutscene || !state.generatedMusic)
			return null;
	} catch (e:Dynamic) {
		return null;
	}
	try {
		if (state.playerStrums != null)
			return state.playerStrums;
	} catch (e:Dynamic) {}
	try {
		for (line in state.strumLines.members) {
			if (line != null && !line.cpu && !line.opponentSide)
				return line;
		}
	} catch (e:Dynamic) {}
	return null;
}

function bind(line) {
	boundLine = line;
	if (line == null || line.members == null)
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
		try {
			line.members[0].cpu = false;
		} catch (e:Dynamic) {}
	}
	if (n > 1) {
		line.members[1].getPressed = function(_s) return down[1];
		line.members[1].getJustPressed = function(_s) return tap[1];
		line.members[1].getJustReleased = function(_s) return rel[1];
		try {
			line.members[1].cpu = false;
		} catch (e:Dynamic) {}
	}
	if (n > 2) {
		line.members[2].getPressed = function(_s) return down[2];
		line.members[2].getJustPressed = function(_s) return tap[2];
		line.members[2].getJustReleased = function(_s) return rel[2];
		try {
			line.members[2].cpu = false;
		} catch (e:Dynamic) {}
	}
	if (n > 3) {
		line.members[3].getPressed = function(_s) return down[3];
		line.members[3].getJustPressed = function(_s) return tap[3];
		line.members[3].getJustReleased = function(_s) return rel[3];
		try {
			line.members[3].cpu = false;
		} catch (e:Dynamic) {}
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

function comboCount() {
	try {
		return PlayState.instance.combo;
	} catch (e:Dynamic) {}
	return 0;
}

function judge(combo:Int) {
	if (combo > lastCombo)
		rating = "good";
	else if (combo < lastCombo)
		rating = "miss";
	lastCombo = combo;
}

function clearLanes() {
	var ch = 0;
	while (ch < 4) {
		etas[ch] = null;
		due[ch] = false;
		sustain[ch] = false;
		ch = ch + 1;
	}
}

function clearWanted() {
	var i = 0;
	while (i < 4) {
		wanted[i] = false;
		i = i + 1;
	}
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

function scan(line, songPos:Float) {
	clearLanes();
	var notes = null;
	try {
		notes = line.notes.members;
	} catch (e:Dynamic) {}
	if (notes == null)
		return;
	var count = notes.length;
	var i = 0;
	while (i < count) {
		var note = notes[i];
		i = i + 1;
		if (note == null || !note.alive)
			continue;
		if (skipNote(note))
			continue;
		var lane = note.strumID;
		if (lane < 0 || lane > 3)
			continue;
		var t = note.strumTime;
		if (note.isSustainNote) {
			if (!note.wasGoodHit && t <= songPos + 80) {
				sustain[lane] = true;
				if (t <= songPos + 10 && t >= songPos - 80)
					due[lane] = true;
			}
			continue;
		}
		if (note.wasGoodHit || note.avoid)
			continue;
		var eta = (t - songPos) * 0.001;
		if (eta > -0.12 && eta < 0.32) {
			if (etas[lane] == null || Math.abs(eta) < Math.abs(etas[lane]))
				etas[lane] = eta;
		}
		if (note.canBeHit || (t <= songPos + 10 && t >= songPos - 80))
			due[lane] = true;
		if (note.tailCount > 0 || note.nextSustain != null)
			sustain[lane] = true;
	}
}

function writeSense(song:Bool, songPos:Float, combo:Int) {
	seq = seq + 1;
	var text = "v=1 song=" + (song ? "1" : "0") + " t=" + songPos + " combo=" + combo + " seq=" + seq + " keys=1 layout=wasd\n";
	text = text + "e=" + num(etas[0]) + "," + num(etas[1]) + "," + num(etas[2]) + "," + num(etas[3]) + "\n";
	text = text + "s=" + bit(sustain[0]) + "," + bit(sustain[1]) + "," + bit(sustain[2]) + "," + bit(sustain[3]) + "\n";
	text = text + "d=" + bit(due[0]) + "," + bit(due[1]) + "," + bit(due[2]) + "," + bit(due[3]) + "\n";
	if (rating != "") {
		text = text + "r=" + rating + "\n";
		rating = "";
	}
	try {
		File.saveContent(sensePath, text);
	} catch (e:Dynamic) {}
	try {
		File.saveContent("mods/fruit-fly/python/fly_fnf_sense.txt", text);
	} catch (e:Dynamic) {}
}

function readPress() {
	var text = null;
	try {
		if (FileSystem.exists(pressPath))
			text = File.getContent(pressPath);
	} catch (e:Dynamic) {}
	if (text == null || text.length < 3) {
		brainAlive = false;
		clearWanted();
		return;
	}
	var live = false;
	var quit = false;
	var stamp = 0.0;
	var bits = [false, false, false, false];
	var parts = text.split(" ");
	var i = 0;
	while (i < parts.length) {
		var part = parts[i];
		i = i + 1;
		if (part.indexOf("alive=") == 0)
			live = part.substr(6) != "0";
		else if (part.indexOf("quit=") == 0)
			quit = part.substr(5) != "0";
		else if (part.indexOf("t=") == 0)
			stamp = Std.parseFloat(part.substr(2));
		else if (part.indexOf("m=") == 0) {
			var m = part.substr(2).split(",");
			var k = 0;
			while (k < 4 && k < m.length) {
				bits[k] = m[k] == "1";
				k = k + 1;
			}
		}
	}
	var age = 99.0;
	if (stamp > 0 && !Math.isNaN(stamp))
		age = (Date.now().getTime() / 1000.0) - stamp;
	if (age > STALE) {
		live = false;
		quit = false;
	}
	brainAlive = live && !quit;
	if (brainAlive) {
		var k = 0;
		while (k < 4) {
			wanted[k] = bits[k];
			k = k + 1;
		}
	} else {
		clearWanted();
	}
}

function trySpawn() {
	if (brainAlive)
		return;
	if (spawnClock < SPAWN_GAP)
		return;
	spawnClock = 0;
	var path = launcherPath();
	if (path == null || path == "") {
		noteSpawn("missing launcher");
		return;
	}
	var abs = makeAbs(path);
	noteSpawn(abs);
	if (!isWin) {
		try {
			Sys.command("/bin/sh", [path, "--detach"]);
		} catch (e:Dynamic) {}
		return;
	}
	try {
		Sys.command("start \"FlyBrainWin\" \"" + abs + "\"");
	} catch (e:Dynamic) {}
}

function makeAbs(path:String) {
	if (path != null && path.indexOf(":") >= 0)
		return backslash(path);
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
	return backslash(cwd + path);
}

function noteSpawn(msg:String) {
	try {
		File.saveContent(tmpDir() + "/fly_fnf_spawn.txt", msg);
	} catch (e:Dynamic) {}
}

function launcherPath() {
	var name = isWin ? "fly_brain.bat" : "fly_brain.sh";
	var roots = ["mods/fruit-fly/python/", "./mods/fruit-fly/python/", "addons/fruit-fly/python/", "./addons/fruit-fly/python/"];
	var i = 0;
	while (i < roots.length) {
		var candidate = roots[i] + name;
		i = i + 1;
		try {
			if (FileSystem.exists(candidate))
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

function backslash(path:String) {
	if (path == null)
		return "";
	return path.split("/").join("\\");
}

function num(v) {
	if (v == null)
		return "";
	return Std.string(v);
}

function bit(v) {
	return v == true ? "1" : "0";
}

function badType(raw) {
	if (raw == null)
		return false;
	var t = Std.string(raw).toLowerCase();
	if (t == "" || t == "null" || t == "normal" || t == "default" || t == "none")
		return false;
	var keys = ["hurt", "mine", "kill", "death", "fake", "bomb", "hazard", "black", "evil", "insta", "spike", "trap", "poison", "shadow", "void", "blood", "nohit", "no-hit", "ghost", "thorn", "danger"];
	var i = 0;
	while (i < keys.length) {
		if (t.indexOf(keys[i]) >= 0)
			return true;
		i = i + 1;
	}
	return false;
}

function darkColor(note) {
	try {
		var n = Std.int(note.color);
		var r = (n >> 16) & 255;
		var g = (n >> 8) & 255;
		var b = n & 255;
		return r < 48 && g < 48 && b < 48 && (r + g + b) < 90;
	} catch (e:Dynamic) {}
	return false;
}

function skipNote(note) {
	if (note == null)
		return true;
	try {
		if (note.avoid == true)
			return true;
	} catch (e:Dynamic) {}
	try {
		if (note.hitCausesMiss == true)
			return true;
	} catch (e:Dynamic) {}
	try {
		if (note.ignoreNote == true)
			return true;
	} catch (e:Dynamic) {}
	try {
		if (note.blockHit == true)
			return true;
	} catch (e:Dynamic) {}
	try {
		if (note.hurtNote == true)
			return true;
	} catch (e:Dynamic) {}
	try {
		if (badType(note.noteType))
			return true;
	} catch (e:Dynamic) {}
	try {
		if (badType(note.noteKind))
			return true;
	} catch (e:Dynamic) {}
	try {
		if (badType(note.kind))
			return true;
	} catch (e:Dynamic) {}
	if (darkColor(note))
		return true;
	return false;
}
