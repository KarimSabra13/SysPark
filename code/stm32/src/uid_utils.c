#include <ctype.h>
#include <string.h>
#include "uid_utils.h"

/* Simplifie et garde 8 hex digits max */
void uid_normalize8(const char *in, char *out, size_t out_sz)
{
    size_t n = 0;
    for (size_t i = 0; in[i] != '\0' && n < 8 && n < out_sz - 1; i++) {
        char c = in[i];
        if (c >= 'a' && c <= 'f') c = (char)(c - 'a' + 'A');
        if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))
            out[n++] = c;
    }
    out[n] = '\0';
}
