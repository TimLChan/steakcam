## alert logic

SteakCam triggers an alert during the following scenarios:

| Scenario        | Description                                                                                     | Prev Timer | Current Timer | Alert |
| --------------- | ----------------------------------------------------------------------------------------------- | ---------- | ------------- | ----- |
| Idle Trigger    | Timer was reset to 6000 and has ticked down                                                     | 6000       | 4500          | Yes   |
| Trigger from 0  | Timer was 0 and has ticked down, usually happens when there are a lot of challenges             | 0          | 4500          | Yes   |
| Decrement       | Timer is continuing to count down                                                               | 4500       | 4400          | No    |
| Timer Finished  | Timer has either hit exactly 0                                                                  | 4400       | 0             | No    |
| Timer has reset | Timer has been reset back to 6000                                                               | 0          | 6000          | No    |
| Unchanged       | The current reading exactly matches what it was from last check                                 | 4400       | 4400          | No    |
| Overlap Trigger | Timer has overlapped with a new challenge and enough time has passed since the last trigger     | 4400       | 4500          | Yes   |
| Overlap Defer   | Timer has overlapped with a new challenge and not enough time has passed since the last trigger | 4400       | 4500          | No    |
| Timer too low   | The current reading is less than the minimum valid trigger time                                 | 6000       | 99            | No    |
| Win (beta)      | The clock has been stopped mid-challenge, see win detection below                               | 3221       | 3221          | Yes*  |
| Already won     | The clock is still stopped on a win that has already been recorded                              | 3221       | 3221          | No    |
| Stopped early   | The clock was stopped within 2 minutes of starting, usually staff starting the wrong timer      | 5959       | 5959          | No    |

\* only sent when `shouldReportWinners` is enabled in `config.json`

### reset timings

The timer is reset in the following scenarios when it is ready to go

- Timer reads 0
- Timer reads 6000

### win detection (beta)

When a contestant finishes the steak, staff stop their clock. If a running clock shows the same reading on two consecutive polls (and that reading isn't `0000` or `6000`), it is recorded as a likely win in the `challenge_wins` table.

- Wins are always recorded in the database. The `shouldReportWinners` flag (default `false`) only controls the live winner alert and the winners line in the end of day wrapup.
- The winner alert includes a screencap of the full camera frame from the first poll that showed the stopped time, so the win can be checked by eye. While `shouldReportWinners` is enabled, the frames from the last 3 polls are kept in `screencaps/` and older ones are deleted.
- A clock stopped within the first 2 minutes (a reading above `5800`) isn't counted. This is usually staff starting the wrong timer and stopping it again.
- Each challenge can only be counted as a win once. The flag is cleared when the clock is reset to `0000` or `6000`, or a new challenge starts on that clock.
- A failed OCR read skips the whole poll, so it doesn't break up the two consecutive readings.
- If the stream stalls and serves the same video segment twice, the poll is skipped. Otherwise every running clock would look stopped.
- Staff sometimes stop a clock for reasons other than a win (e.g. a forfeit), so treat these as "likely wins" rather than confirmed winners.
