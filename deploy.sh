#!/bin/bash
cd /root/projects/TimeWoven
git pull origin main
systemctl restart timewoven
echo "Deployed at $(date)"
