# Shared helpers for the simswitch scripts: JSON escaping, validated UCI
# values and the profile table. Sourced, never run.

# --------------------------------------------------------------------- JSON
JSON_ESC='function jesc(s,   o, i, n, c) {
    o = ""; n = length(s)
    for (i = 1; i <= n; i++) { c = substr(s, i, 1); o = o ((c in JE) ? JE[c] : c) }
    return o
}
BEGIN {
    for (i = 1; i < 32; i++) JE[sprintf("%c", i)] = sprintf("\\u%04x", i)
    JE[sprintf("%c", 127)] = "\\u007f"
    JE["\\"] = "\\\\"; JE["\""] = "\\\""; JE["\n"] = "\\n"; JE["\t"] = "\\t"; JE["\r"] = "\\r"
}'
json_str() {
    printf '%s\n' "$1" | awk "$JSON_ESC"'
        BEGIN { printf "\"" } { printf "%s%s", (NR > 1 ? "\\n" : ""), jesc($0) } END { printf "\"" }'
}
json_str_or_null() { if [ -n "$1" ]; then json_str "$1"; else echo null; fi; }

# ---------------------------------------------------------- uci allow-lists
uci_get() { uci -q get "simswitch.main.$1" 2>/dev/null || true; }

# safe_iface NAME DEFAULT: an interface name (at most 15 characters, starting
# with a letter or digit), else DEFAULT
safe_iface() {
    case $1 in
        ''|[!A-Za-z0-9]*|*[!A-Za-z0-9_.-]*) printf '%s\n' "$2" ;;
        *) if [ ${#1} -le 15 ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi ;;
    esac
}

# safe_tty PATH DEFAULT: an AT tty under /dev, else DEFAULT
safe_tty() {
    case $1 in
        /dev/tty[A-Za-z0-9_]*|/dev/wwan[A-Za-z0-9_]*)
            case ${1#/dev/} in */*|*[!A-Za-z0-9_]*) printf '%s\n' "$2" ;; *) printf '%s\n' "$1" ;; esac ;;
        *) printf '%s\n' "$2" ;;
    esac
}

# safe_program PATH: an absolute, executable program without whitespace, else
# nothing
safe_program() {
    case $1 in
        /*) ;;
        *) return 0 ;;
    esac
    case $1 in
        *[!A-Za-z0-9_./-]*|*/../*|*/..|..) return 0 ;;
    esac
    [ -x "$1" ] && printf '%s\n' "$1"
}

# ------------------------------------------------------------------ profiles
profile_sections() {
    uci -q show simswitch 2>/dev/null | sed -n 's/^simswitch\.\([^.=]*\)=profile$/\1/p'
}
profile_get() { uci -q get "simswitch.$1.$2" 2>/dev/null || true; }

profile_code_ok() {
    case $1 in
        [0-9][0-9][0-9][0-9]) return 0 ;;
    esac
    return 1
}

profile_find() {
    for _s in $(profile_sections); do
        [ "$(profile_get "$_s" code)" = "$1" ] && return 0
    done
    return 1
}

profile_label() {
    _l=$(profile_get "$1" label)
    [ -n "$_l" ] || _l="Profile $(profile_get "$1" code)"
    printf '%s' "$_l"
}

profile_label_by_code() {
    for _s in $(profile_sections); do
        [ "$(profile_get "$_s" code)" = "$1" ] || continue
        profile_label "$_s"
        return 0
    done
    return 1
}

# ---------------------------------------------------------------- runtime
# lock_live DIR: the lock has a pid and that process is still running
lock_live() {
    [ -d "$1" ] || return 1
    _p=$(cat "$1/pid" 2>/dev/null)
    [ -n "$_p" ] && kill -0 "$_p" 2>/dev/null
}

# ensure_dir DIR: DIR exists, is ours and is private, or fail
ensure_dir() {
    [ -L "$1" ] && return 1
    (umask 077; mkdir -p "$1") 2>/dev/null || return 1
    [ -d "$1" ] && [ -O "$1" ] || return 1
    chmod 700 "$1" 2>/dev/null
}
