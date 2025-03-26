#!/bin/bash
for file in /napcat/onebot11*.json; do
    if [ -f "$file" ]; then
        cp "/tanpopo/onebot11.json" "$file"
    fi
done