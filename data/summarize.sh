#!/bin/bash
for data_dir in *
do
  if [ ! -d "${data_dir}" ]
  then
    continue
  fi
  if [ -f "${data_dir}/labels.csv" ]
  then
    ../summarize.py "$data_dir"
  else
    echo No labels file in ${data_dir}.
  fi
  echo
done
