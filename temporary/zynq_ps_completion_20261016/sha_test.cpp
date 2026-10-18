#include "camera/int8/sha256.h"
#include <cstdio>
#include <io.h>
#include <fcntl.h>
int main(){_setmode(_fileno(stdin),_O_BINARY);Sha256 sha;unsigned char data[4096];size_t n;while((n=std::fread(data,1,sizeof(data),stdin)))sha.update(data,n);unsigned char out[32];sha.finish(out);for(unsigned i=0;i<32;++i)std::printf("%02x",out[i]);return 0;}

