local spawned = false
local seq = 0
local lastRating = ""
local prev = {false, false, false, false}

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
    local alive = false
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
    hx("game.cpuControlled = false;")
    hx("game.cpu = false;")
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
    local stamp = 0
    if text == nil or text == "" then
        return false, down
    end
    for part in string.gmatch(text, "%S+") do
        if string.sub(part, 1, 6) == "alive=" then
            local v = string.sub(part, 7)
            if v ~= "0" and v ~= "false" then
                alive = true
            end
        elseif string.sub(part, 1, 2) == "t=" then
            stamp = tonumber(string.sub(part, 3)) or 0
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
    if stamp > 0 then

    end
    if not alive then
        down = {false, false, false, false}
    end
    return alive, down
end

local function applyFlyKeys(down)
    for i = 0, 3 do
        local on = down[i + 1] == true
        local was = prev[i + 1] == true
        if on and not was then
            hx("game.keysPressed[" .. i .. "] = true;")
            hx("game.keyPressed(" .. i .. ");")
        elseif (not on) and was then
            hx("game.keysPressed[" .. i .. "] = false;")
            hx("game.keyReleased(" .. i .. ");")
        elseif on then
            hx("game.keysPressed[" .. i .. "] = true;")
        end
        prev[i + 1] = on
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
            must = getPropertyFromGroup("notes", i, "mustPress") == true
            hit = getPropertyFromGroup("notes", i, "wasGoodHit") == true
            sus = getPropertyFromGroup("notes", i, "isSustainNote") == true
            data = tonumber(getPropertyFromGroup("notes", i, "noteData")) or 0
            strum = tonumber(getPropertyFromGroup("notes", i, "strumTime")) or 0
            alive = getPropertyFromGroup("notes", i, "alive") ~= false
        end)
        local skip = false
        pcall(function()
            if getPropertyFromGroup("notes", i, "avoid") == true then
                skip = true
            end
            if getPropertyFromGroup("notes", i, "hitCausesMiss") == true then
                skip = true
            end
            if getPropertyFromGroup("notes", i, "ignoreNote") == true then
                skip = true
            end
            if getPropertyFromGroup("notes", i, "blockHit") == true then
                skip = true
            end
            local ntype = string.lower(tostring(getPropertyFromGroup("notes", i, "noteType") or ""))
            if ntype ~= "" and ntype ~= "normal" and ntype ~= "default" and ntype ~= "none" and ntype ~= "null" then
                local bad = { "hurt", "mine", "kill", "death", "fake", "bomb", "hazard", "black", "evil", "insta", "spike", "trap", "poison", "shadow", "void", "blood", "nohit", "no-hit", "ghost", "thorn", "danger" }
                local k = 1
                while k <= #bad do
                    if string.find(ntype, bad[k], 1, true) then
                        skip = true
                    end
                    k = k + 1
                end
            end
            local r = tonumber(getPropertyFromGroup("notes", i, "rgbShader.r"))
            local g = tonumber(getPropertyFromGroup("notes", i, "rgbShader.g"))
            local b = tonumber(getPropertyFromGroup("notes", i, "rgbShader.b"))
            if r ~= nil and g ~= nil and b ~= nil then
                if r <= 1 and g <= 1 and b <= 1 then
                    if r < 0.18 and g < 0.18 and b < 0.18 then
                        skip = true
                    end
                elseif r < 46 and g < 46 and b < 46 then
                    skip = true
                end
            end
        end)
        local lane = (data % 4) + 1
        if must and alive and not skip then
            if sus then
                if strum <= songPos + 80 then
                    sustain[lane] = true
                    if strum <= songPos + 10 and strum >= songPos - 80 then
                        due[lane] = true
                    end
                end
            elseif not hit then
                local eta = (strum - songPos) * 0.001
                if eta > -0.12 and eta < 0.32 then
                    if etas[lane] == "" or math.abs(eta) < math.abs(tonumber(etas[lane]) or 99) then
                        etas[lane] = tostring(eta)
                    end
                end
                if strum <= songPos + 10 and strum >= songPos - 80 then
                    due[lane] = true
                end
                local slen = 0
                pcall(function()
                    slen = tonumber(getPropertyFromGroup("notes", i, "sustainLength")) or 0
                end)
                if slen > 80 then
                    sustain[lane] = true
                end
            end
        end
        i = i + 1
    end
    return songPos, etas, sustain, due
end

function onCreate()
    spawnBrain()
    killBotplay()
end

function onCreatePost()
    spawnBrain()
    killBotplay()
end

function onUpdate(elapsed)
    spawnBrain()
    killBotplay()
    local inSong = false
    pcall(function()
        inSong = getProperty("generatedMusic") == true and getProperty("inCutscene") ~= true and getProperty("paused") ~= true
    end)
    local combo = 0
    pcall(function()
        combo = getProperty("combo")
    end)
    if not inSong then
        writeSense(false, 0, 0, {"", "", "", ""}, {false, false, false, false}, {false, false, false, false}, "")
        applyFlyKeys({false, false, false, false})
        return
    end
    local songPos, etas, sustain, due = scanNotes()
    local rating = lastRating
    lastRating = ""
    writeSense(true, songPos, combo, etas, sustain, due, rating)
    local alive, down = pullPress()
    if not alive then
        applyFlyKeys({false, false, false, false})
        return
    end
    applyFlyKeys(down)
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
