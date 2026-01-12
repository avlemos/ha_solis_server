[![HACS Compliance](https://github.com/avlemos/ha_solis_client/actions/workflows/validate.yaml/badge.svg "HACS Compliance")](https://github.com/avlemos/ha_solis_client/actions/workflows/validate.yaml)
[![Validate with hassfest](https://github.com/avlemos/ha_solis_client/actions/workflows/hassfest.yaml/badge.svg "hassfest Compliance")](https://github.com/avlemos/ha_solis_client/actions/workflows/hassfest.yaml)

# Intro

This is a project for [Home Assistant](https://github.com/home-assistant) which enables you to connect to Solis/Solarman logger/inverter system, by using the **Remote Server** configuration on its web interface (this module serves as a server).


# Usage
Just pick the port where you want to listen for the requests using the HA interface, and every 5 minutes, as long as your inverter is active (won't work with 0 solar production), you should be good to go.

# Screenshot

<img width="329" height="767" alt="image" src="https://github.com/user-attachments/assets/c424bd82-d45b-4fdb-934b-79b33c974a03" />


# Ugh
It's not lost in me, that we actually create a Server here, and the Logger is the actual client