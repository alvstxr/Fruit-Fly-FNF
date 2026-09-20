local spawned = false
local seq = 0
local lastRating = ""
local prev = {false, false, false, false}
local holdUntil = {0, 0, 0, 0}
local lastDown = {false, false, false, false}
local lastAlive = false
local senseClock = 0
local pressClock = 0
local botClock = 99

local function isWindows()
    if os.getenv("OS") == "Windows_NT" then
        return true
    end
    return package.config:sub(1, 1) == "\\"
end

local function tempDir()
    if isWindows() then
        local t = os.getenv("TEMP") or os.getenv("TMP")
        if t ~= nil and t ~= "" then
            return t
        end
        return "."
    end
    return "/tmp"
end

local function exists(path)
    local f = io.open(path, "r")
    if f then
        f:close()
        return true
    end
    return false
end

local function writeAll(path, text)
    local f = io.open(path, "w")
    if not f then
        return
    end
    f:write(text)
    f:close()
end

local function readAll(path)
    local f = io.open(path, "r")
    if not f then
        return ""
    end
    local t = f:read("*a")
    f:close()
    return t or ""
end

local function findPythonDir()
    local cands = {
        "mods/fruit-fly/python",
        "addons/fruit-fly/python",
        "./mods/fruit-fly/python",
        "./addons/fruit-fly/python",
        "../Resources/mods/fruit-fly/python",
        "../../Resources/mods/fruit-fly/python",
        "../mods/fruit-fly/python",
        "../../mods/fruit-fly/python",
        "../../../mods/fruit-fly/python",
        "python"
    }
    for i = 1, #cands do
        if exists(cands[i] .. "/fly_bridge.py") or exists(cands[i] .. "/fly_brain.bat") or exists(cands[i] .. "/fly_brain.sh") then
            return cands[i]
        end
    end
    return nil
end

local function spawnBrain()
    if spawned then
        return
    end
    local text = readAll(tempDir() .. "/fly_fnf_press.txt")
    if text ~= nil and string.find(text, "alive=1", 1, true) then
        spawned = true
        return
    end
    spawned = true
    local dir = findPythonDir()
    if dir == nil then
        return
    end
    if isWindows() then
        local bat = dir .. "/fly_brain.bat"
        if not exists(bat) then
            bat = dir .. "/run-fly-brain.bat"
        end
        if exists(bat) then
            os.execute('start "FlyBrainWin" "' .. bat:gsub("/", "\\") .. '"')
        else
            os.execute('start "FlyBrainWin" py -3 "' .. (dir .. "/fly_bridge.py"):gsub("/", "\\") .. '"')
        end
        return
    end
    local sh = dir .. "/fly_brain.sh"
    if exists(sh) then
        os.execute('/bin/sh "' .. sh .. '" --detach')
        return
    end
    os.execute('/bin/sh -c "nohup python3 \\"' .. dir .. '/fly_bridge.py\\" >/tmp/fly_fnf_brain.log 2>&1 &"')
end

local function hx(code)
    if runHaxeCode then
        pcall(runHaxeCode, code)
    end
end

local function killBotplay()
    pcall(setProperty, "cpuControlled", false)
    pcall(setProperty, "botplay", false)
    pcall(setProperty, "cpu", false)
end

local function flag(v)
    if v then
        return "1"
    end
    return "0"
end

local function writeSense(song, t, combo, etas, sustain, due, rating)
    seq = seq + 1
    local lines = {
        "v=1 song=" .. (song and "1" or "0") .. " t=" .. tostring(t or 0) .. " combo=" .. tostring(combo or 0) .. " seq=" .. tostring(seq) .. " keys=1 layout=wasd_arrows",
        "e=" .. (etas[1] or "") .. "," .. (etas[2] or "") .. "," .. (etas[3] or "") .. "," .. (etas[4] or ""),
        "s=" .. flag(sustain[1]) .. "," .. flag(sustain[2]) .. "," .. flag(sustain[3]) .. "," .. flag(sustain[4]),
        "d=" .. flag(due[1]) .. "," .. flag(due[2]) .. "," .. flag(due[3]) .. "," .. flag(due[4])
    }
    if rating ~= nil and rating ~= "" then
        lines[#lines + 1] = "r=" .. tostring(rating)
    end
    writeAll(tempDir() .. "/fly_fnf_sense.txt", table.concat(lines, "\n") .. "\n")
end

local function pullPress()
    local text = readAll(tempDir() .. "/fly_fnf_press.txt")
    local alive = false
    local down = {false, false, false, false}
    if text == nil or text == "" then
        return lastAlive, lastDown
    end
    for part in string.gmatch(text, "%S+") do
        if string.sub(part, 1, 6) == "alive=" then
            local v = string.sub(part, 7)
            if v ~= "0" and v ~= "false" then
                alive = true
            end
        elseif string.sub(part, 1, 2) == "m=" then
            local i = 1
            for bit in string.gmatch(string.sub(part, 3), "[^,]+") do
                if i <= 4 then
                    down[i] = bit ~= "0" and bit ~= "false" and bit ~= ""
                end
                i = i + 1
            end
        end
    end
    if not alive then
        down = {false, false, false, false}
    end
    lastAlive = alive
    lastDown = down
    return alive, down
end

local function badType(raw)
    local t = string.lower(tostring(raw or ""))
    if t == "" or t == "null" or t == "normal" or t == "default" or t == "none" then
        return false
    end
    local bad = { "hurt", "mine", "kill", "death", "fake", "bomb", "hazard", "black", "evil", "insta", "spike", "trap", "poison", "shadow", "void", "blood", "nohit", "no-hit", "ghost", "thorn", "danger" }
    local k = 1
    while k <= #bad do
        if string.find(t, bad[k], 1, true) then
            return true
        end
        k = k + 1
    end
    return false
end

local function applyFlyKeys(down)
    local w0 = down[1] and "true" or "false"
    local w1 = down[2] and "true" or "false"
    local w2 = down[3] and "true" or "false"
    local w3 = down[4] and "true" or "false"
    local pos = 0
    pcall(function()
        pos = getSongPosition()
    end)
    hx("var g = game; if (g == null) g = PlayState.instance; if (g != null) { if (g.keysPressed != null) { g.keysPressed[0] = " .. w0 .. "; g.keysPressed[1] = " .. w1 .. "; g.keysPressed[2] = " .. w2 .. "; g.keysPressed[3] = " .. w3 .. "; } var want = [" .. w0 .. "," .. w1 .. "," .. w2 .. "," .. w3 .. "]; var pos = " .. tostring(pos) .. "; if (g.notes != null) { for (n in g.notes) { if (n == null || !n.mustPress || !n.alive) continue; var lane = n.noteData % 4; if (lane < 0) lane = -lane; lane = lane % 4; if (!want[lane]) continue; if (n.isSustainNote) { if (!n.wasGoodHit && n.strumTime <= pos + 40 && n.strumTime >= pos - 90) g.goodNoteHit(n); continue; } if (n.wasGoodHit) continue; var diff = n.strumTime - pos; if (diff <= 46 && diff >= -40) g.goodNoteHit(n); } } }")
    for i = 0, 3 do
        prev[i + 1] = down[i + 1] == true
    end
end

local function scanNotes()
    local etas = {"", "", "", ""}
    local due = {false, false, false, false}
    local sustain = {false, false, false, false}
    local songPos = 0
    pcall(function()
        songPos = getSongPosition()
    end)
    local n = 0
    pcall(function()
        n = getProperty("notes.length")
    end)
    if n == nil then
        n = 0
    end
    local i = 0
    while i < n do
        local must, hit, sus, data, strum, alive = false, false, false, 0, 0, true
        pcall(function()
            must = getPropertyFromGroup("notes", i, "mustPress")
            hit = getPropertyFromGroup("notes", i, "wasGoodHit")
            sus = getPropertyFromGroup("notes", i, "isSustainNote")
            data = tonumber(getPropertyFromGroup("notes", i, "noteData")) or 0
            strum = tonumber(getPropertyFromGroup("notes", i, "strumTime")) or 0
            alive = getPropertyFromGroup("notes", i, "alive")
        end)
        local skip = false
        pcall(function()
            if getPropertyFromGroup("notes", i, "hitCausesMiss") then
                skip = true
            end
            if badType(getPropertyFromGroup("notes", i, "noteType")) then
                skip = true
            end
        end)
        local lane = (math.abs(data) % 4) + 1
        if must and alive ~= false and not skip then
            if sus then
                if strum <= songPos + 50 and strum >= songPos - 200 then
                    sustain[lane] = true
                    if holdUntil[lane] < strum + 80 then
                        holdUntil[lane] = strum + 80
                    end
                end
            elseif not hit then
                local diff = strum - songPos
                if diff > -40 and diff < 80 then
                    if etas[lane] == "" or math.abs(diff) < math.abs((tonumber(etas[lane]) or 99) * 1000) then
                        etas[lane] = tostring(diff * 0.001)
                    end
                end
                if diff <= 32 and diff >= -28 then
                    due[lane] = true
                end
                local slen = 0
                pcall(function()
                    slen = tonumber(getPropertyFromGroup("notes", i, "sustainLength")) or 0
                end)
                if slen > 80 then
                    local endT = strum + slen
                    if songPos >= strum - 32 and songPos <= endT + 40 then
                        holdUntil[lane] = endT
                        sustain[lane] = true
                    end
                end
            end
        end
        i = i + 1
    end
    local lane = 1
    while lane <= 4 do
        if songPos < holdUntil[lane] then
            sustain[lane] = true
        else
            holdUntil[lane] = 0
        end
        lane = lane + 1
    end
    return songPos, etas, sustain, due
end

function onCreate()
    killBotplay()
end

function onCreatePost()
    spawnBrain()
    killBotplay()
end

function onUpdate(elapsed)
    spawnBrain()
    local dt = tonumber(elapsed) or 0.016
    if dt <= 0 or dt > 1 then
        dt = 0.016
    end
    botClock = botClock + dt
    if botClock >= 2 then
        botClock = 0
        killBotplay()
    end
    senseClock = senseClock + dt
    pressClock = pressClock + dt
    local inSong = false
    pcall(function()
        inSong = getProperty("inCutscene") ~= true and getProperty("paused") ~= true
        if getProperty("generatedMusic") == false then
            local n = getProperty("notes.length") or 0
            if n < 1 then
                inSong = false
            end
        end
    end)
    local combo = 0
    pcall(function()
        combo = getProperty("combo")
    end)
    if not inSong then
        if senseClock >= 0.25 then
            senseClock = 0
            holdUntil = {0, 0, 0, 0}
            writeSense(false, 0, 0, {"", "", "", ""}, {false, false, false, false}, {false, false, false, false}, "")
            applyFlyKeys({false, false, false, false})
        end
        return
    end
    if senseClock >= 0.012 then
        senseClock = 0
        local songPos, etas, sustain, due = scanNotes()
        local rating = lastRating
        lastRating = ""
        writeSense(true, songPos, combo, etas, sustain, due, rating)
    end
    if pressClock >= 0.012 then
        pressClock = 0
        local alive, down = pullPress()
        if not alive then
            applyFlyKeys({false, false, false, false})
            return
        end
        applyFlyKeys(down)
    end
end

function onDestroy()
    writeSense(false, 0, 0, {"", "", "", ""}, {false, false, false, false}, {false, false, false, false}, "")
    applyFlyKeys({false, false, false, false})
end

function goodNoteHit(id, direction, noteType, isSustainNote)
    if isSustainNote then
        return
    end
    local rating = nil
    pcall(function()
        rating = getPropertyFromGroup("notes", id, "rating")
    end)
    if rating == nil or rating == "" then
        pcall(function()
            rating = getProperty("ratingName")
        end)
    end
    lastRating = tostring(rating or "sick")
end

function noteMiss(id, direction, noteType, isSustainNote)
    lastRating = "miss"
end

function noteMissPress(direction)
    lastRating = "miss"
end
