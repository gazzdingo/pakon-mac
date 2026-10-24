/* Boards: motor basics (Task 7): stop. There is no jog (PSI has none); film moves are Task 8's pk_film_move. Ported from v1
 * pakon_commands.py motor_stop and pakon_scan.py safe_stop (retried). */
#include "boards/boards.h"

pk_status pk_motor_stop(pk_boards *b) {
    if (!b) return PK_E_ARG;
    pk_status s = PK_E_IO;
    for (int i = 0; i < pkb_attempts(b); i++) {       /* v1 safe_stop: same count as lamp off */
        s = pk_link_command(b->link, b->motor, PKB_CMD_MOTOR_STOP);
        if (s == PK_OK || pkb_status_is_final(s)) return s;
        if (i + 1 < pkb_attempts(b)) pkb_sleep_ms(PKB_RETRY_PAUSE_MS);
    }
    return s;
}
