#ifndef PKV_H
#define PKV_H
#include <stddef.h>

/* PKV1 vector files; format written by lab/vectors/pkv.py.
   dtype: 1 u8, 2 i16, 3 u16, 4 i32, 5 f32, 6 f64. */
typedef struct {
    char name[64];
    int dtype;
    int ndim;
    int dims[4];
    size_t n;     /* element count */
    void *data;   /* a malloc'd copy owned by the file; valid until pkv_close */
} pkv_array;

typedef struct pkv_file pkv_file;

pkv_file *pkv_open(const char *path);                 /* NULL on error */
const pkv_array *pkv_get(const pkv_file *f, const char *name);
void pkv_close(pkv_file *f);
/* A u8 array holding comma-separated ids (e.g. a truth file's run names): the number of ids, and the index of `id`
   (-1 if absent or the array is missing). */
int pkv_list_count(const pkv_file *f, const char *list);
int pkv_list_index(const pkv_file *f, const char *list, const char *id);
#endif
