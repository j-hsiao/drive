#!/bin/bash

# Add the drive command for google drive.
#

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]
then
	if [[ "${BASH_SOURCE[0]}" != /* ]]
	then
		. "${PWD}/${BASH_SOURCE[0]}" "${@}"
		return
	fi
	export PYTHONPATH
	if [[ "${PYTHONPATH}" != ?(*:)"${BASH_SOURCE[0]%/scripts/*}/src"?(:*) ]]
	then
		PYTHONPATH="${BASH_SOURCE[0]%/scripts/*}/src${PYTHONPATH:+:${PYTHONPATH}}"
	fi
	. <(py -m pydrive.googledrive "${@}")
fi
