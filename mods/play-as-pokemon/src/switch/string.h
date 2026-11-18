/* Freestanding string.h for the Switch build: switch_host.c has the three functions play_as_pokemon.c uses. */
#pragma once
#include <stddef.h>
void *memset(void *s, int c, size_t n);
void *memcpy(void *d, const void *s, size_t n);
int strcmp(const char *a, const char *b);
