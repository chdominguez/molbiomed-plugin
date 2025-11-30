#!/bin/bash

echo "Building plugin..."

rm molbiomed.hp

rm -rf molbiomed/deps

zip -r molbiomed.hp molbiomed
