_bosectl() {
  local cur prev words cword
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"

  local commands="quiet aware immersion cinema profiles profile switch cnc anc wind eq spatial name anr sidetone multipoint autopause autoanswer prompts source route pair off status battery current buttons dump raw"

  if [[ ${COMP_CWORD} -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
    return 0
  fi

  case "${COMP_WORDS[1]}" in
    anc|wind|multipoint|autopause|autoanswer|prompts)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "on off" -- "${cur}") )
      ;;
    cnc)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "0 1 2 3 4 5 6 7 8 9 10" -- "${cur}") )
      ;;
    eq)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "flat get" -- "${cur}") )
      ;;
    spatial)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "off room head" -- "${cur}") )
      ;;
    sidetone)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "off low medium high" -- "${cur}") )
      ;;
    anr)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "off high wind low" -- "${cur}") )
      ;;
    switch)
      [[ ${COMP_CWORD} -eq 2 ]] && COMPREPLY=( $(compgen -W "quiet aware immersion cinema" -- "${cur}") )
      ;;
    buttons)
      if [[ ${COMP_CWORD} -eq 2 ]]; then
        COMPREPLY=( $(compgen -W "set" -- "${cur}") )
      elif [[ ${COMP_CWORD} -eq 3 && "${prev}" == "set" ]]; then
        COMPREPLY=( $(compgen -W "NotConfigured VPA ANC BatteryLevel PlayPause IncreaseCNC DecreaseCNC ToggleWakeWord SwitchDevice ConversationMode TrackForward TrackBack FetchNotifications WindMode Disabled ClientInteraction SpotifyGo ModesCarousel SpatialAudioMode LineInSwitch Linking" -- "${cur}") )
      fi
      ;;
    profile)
      if [[ ${COMP_CWORD} -eq 2 ]]; then
        COMPREPLY=( $(compgen -W "set create add rm delete del" -- "${cur}") )
      elif [[ ${COMP_CWORD} -ge 4 ]]; then
        COMPREPLY=( $(compgen -W "cnc= spatial= wind= anc= name=" -- "${cur}") )
      fi
      ;;
  esac
}

complete -F _bosectl bosectl bmapctl
