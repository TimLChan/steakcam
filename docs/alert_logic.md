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

### reset timings

The timer is reset in the following scenarios when it is ready to go

- Timer reads 0
- Timer reads 6000