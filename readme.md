## steakcam

The Big Texan is known for the 72oz Steak Challenge which involves eating a 72oz steak, a whole heap of sides, and a drink in an hour.

There is a [Big Texan 72oz Steak Challenge live stream](https://www.bigtexan.com/live-stream/) for these shenanigans. The Big Texan are providing a 24/7 video only stream on AngelCam which is a direct feed into the restaurant. They have unfortunately stopped streaming on YouTube so it is no longer possible to get notifications for when someone is participating in the challenge. 

Out of necessity, this script has been built to provide steak challenge alerts. 

### how this works

1. finds the m3u8 playlist on the 24/7 stream
2. downloads the last segment in the playlist
3. splits out each of the clocks individually as images
4. for each of the image, performs ocr to extract the text
5. sends an alert of the timer goes from 60:00 -> something else

The process repeats every minute to try catch changes to the clock

## why

bored

## to-do

- [x] logic to parse and find the m3u8
- [x] logic to download the video segment
- [x] logic to split out the individual clocks
- [x] finetuning ocr model
- [x] logic to ocr the image
- [x] track changes to the clocks
- [ ] send an alert on discord