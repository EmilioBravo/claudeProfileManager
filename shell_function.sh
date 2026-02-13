
# claudeProfileManager shell function — auto-source env on profile switch
claudeProfileManager() {
    command claudeProfileManager "$@"
    if [ -f ~/.config/claudeProfileManager/active_env ]; then
        source ~/.config/claudeProfileManager/active_env
    fi
}
