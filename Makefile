CC ?= gcc

CFLAGS := -Wall -Wextra -O2 -fPIC
LDFLAGS := -shared
LDLIBS := -ldl -pthread

TARGET := libsvxlink_tx_tap.so
SOURCE := src/svxlink_tx_tap.c

.PHONY: all clean check

all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LDLIBS)

check: $(TARGET)
	file $(TARGET)
	nm -D $(TARGET) | grep -E 'snd_pcm_writei|dlsym'

clean:
	rm -f $(TARGET)
