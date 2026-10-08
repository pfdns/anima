#!/bin/bash

URL="https://hls.dramahot.top/v/scxqicy/4a0xe95o0l/xgltord6uz/jl3msklfb1w2ya/subs/feluv7hfr4bqzawq.vtt"
REFERER="https://zokoanime.video/"

echo "=== Test 1: Minimal (no headers) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$URL"
echo ""

echo "=== Test 2: Only Referer ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: $REFERER" \
  "$URL"
echo ""

echo "=== Test 3: Referer + User-Agent ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: $REFERER" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  "$URL"
echo ""

echo "=== Test 4: Full browser headers ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: $REFERER" \
  -H "Origin: https://zokoanime.video" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  -H "Accept: */*" \
  -H "Accept-Language: en-US,en;q=0.9" \
  -H "Accept-Encoding: gzip, deflate, br" \
  -H "Connection: keep-alive" \
  -H "Sec-Fetch-Dest: empty" \
  -H "Sec-Fetch-Mode: cors" \
  -H "Sec-Fetch-Site: cross-site" \
  "$URL"
echo ""

echo "=== Test 5: Referer بدون اسلش آخر ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: https://zokoanime.video" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  "$URL"
echo ""

echo "=== Test 6: Referer با www ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: https://www.zokoanime.video/" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  "$URL"
echo ""

echo "=== Test 7: Referer = hianime.at ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: https://hianime.at/" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  "$URL"
echo ""

echo "=== Test 8: Origin + Referer (بدون Accept-Encoding) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Referer: $REFERER" \
  -H "Origin: https://zokoanime.video" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Accept: */*" \
  "$URL"
echo ""
