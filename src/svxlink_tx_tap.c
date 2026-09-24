#define _GNU_SOURCE

#include <alsa/asoundlib.h>
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define TAP_SOCKET_PATH "/run/svxlink-audio-monitor/tx.sock"

/*
 * Current tested TX PCM format:
 *
 *   S16_LE
 *   2 channels
 *   48000 Hz
 *
 * Therefore:
 *
 *   2 bytes/sample × 2 channels = 4 bytes/frame
 */
#define TX_BYTES_PER_FRAME 4U

static snd_pcm_sframes_t (*real_snd_pcm_writei)(
    snd_pcm_t *,
    const void *,
    snd_pcm_uframes_t
) = NULL;

static pthread_once_t init_once = PTHREAD_ONCE_INIT;

static int tap_socket = -1;
static struct sockaddr_un tap_address;

static void initialise(void)
{
    real_snd_pcm_writei = dlsym(RTLD_NEXT, "snd_pcm_writei");

    tap_socket = socket(
        AF_UNIX,
        SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC,
        0
    );

    if (tap_socket < 0) {
        return;
    }

    memset(&tap_address, 0, sizeof(tap_address));
    tap_address.sun_family = AF_UNIX;

    strncpy(
        tap_address.sun_path,
        TAP_SOCKET_PATH,
        sizeof(tap_address.sun_path) - 1
    );
}

snd_pcm_sframes_t snd_pcm_writei(
    snd_pcm_t *pcm,
    const void *buffer,
    snd_pcm_uframes_t size
)
{
    pthread_once(&init_once, initialise);

    if (real_snd_pcm_writei == NULL) {
        errno = ENOSYS;
        return -1;
    }

    /*
     * The real transmitter path is always serviced first.
     */
    snd_pcm_sframes_t result =
        real_snd_pcm_writei(pcm, buffer, size);

    /*
     * Only copy frames ALSA reports as accepted.
     *
     * The monitor path is deliberately non-blocking and
     * completely disposable. Failure here must never alter
     * the result returned to SvxLink.
     */
    if (result > 0 && tap_socket >= 0) {
        const size_t bytes =
            (size_t)result * TX_BYTES_PER_FRAME;

        (void)sendto(
            tap_socket,
            buffer,
            bytes,
            MSG_DONTWAIT | MSG_NOSIGNAL,
            (const struct sockaddr *)&tap_address,
            sizeof(tap_address)
        );
    }

    return result;
}
