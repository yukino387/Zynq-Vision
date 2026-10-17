#include "xqspips.h"
#include "xparameters.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include "int8/sha256.h"
#include <cstring>
// JTAG-only utility for this board's W25Q256. Only the first 16 MiB is addressable.
struct Control { uint32_t operation,bytes,state,progress,error,jedec;uint8_t sha256[32]; };
static XQspiPs qspi;
static uint8_t tx[4104],rx[4104];
static volatile Control* const control=reinterpret_cast<volatile Control*>(0x03000000);
static uint8_t* const image=reinterpret_cast<uint8_t*>(0x08000000);
static bool transfer(unsigned n,bool receive=true){return XQspiPs_PolledTransfer(&qspi,tx,receive?rx:nullptr,n)==XST_SUCCESS;}
static bool idle(unsigned seconds){
 XTime begin,now;XTime_GetTime(&begin);
 do{tx[0]=5;tx[1]=0;if(!transfer(2))return false;if(!(rx[1]&1))return true;XTime_GetTime(&now);}while(now-begin<seconds*COUNTS_PER_SECOND);
 return false;
}
static bool enable_write(){tx[0]=6;if(!transfer(1))return false;tx[0]=5;tx[1]=0;return transfer(2)&&(rx[1]&2);}
static void address(uint8_t command,unsigned offset){tx[0]=command;tx[1]=offset>>16;tx[2]=offset>>8;tx[3]=offset;}
static bool read(unsigned offset,unsigned count){address(3,offset);std::memset(tx+4,0,count);return transfer(count+4);}
static unsigned execute(){
 const uint32_t size=control->bytes,operation=control->operation;
 if(!size||size>=16u*1024*1024||(operation!=1&&operation!=2))return 1;
 auto config=XQspiPs_LookupConfig(XPAR_XQSPIPS_0_BASEADDR);
 if(!config||XQspiPs_CfgInitialize(&qspi,config,config->BaseAddress)!=XST_SUCCESS)return 2;
 XQspiPs_SetOptions(&qspi,XQSPIPS_MANUAL_START_OPTION|XQSPIPS_FORCE_SSELECT_OPTION|XQSPIPS_HOLD_B_DRIVE_OPTION);
 XQspiPs_SetClkPrescaler(&qspi,XQSPIPS_CLK_PRESCALE_8);XQspiPs_SetSlaveSelect(&qspi);
 tx[0]=0x9f;tx[1]=tx[2]=tx[3]=0;if(!transfer(4))return 2;
 const uint32_t id=(uint32_t(rx[1])<<16)|(uint32_t(rx[2])<<8)|rx[3];control->jedec=id;
 if(id!=0xef4019)return 3;
 tx[0]=0xe9;if(!transfer(1))return 2;
 // W25Q256FV can retain EAR=1 after E9. Select the BootROM's low bank.
 if(!enable_write())return 4;tx[0]=0xc5;tx[1]=0;if(!transfer(2)||!idle(1))return 5;
 tx[0]=4;if(!transfer(1))return 2;tx[0]=0xc8;tx[1]=0;if(!transfer(2)||rx[1])return 7;
 if(operation==1){
  for(unsigned offset=0;offset<size;offset+=4096){unsigned n=size-offset<4096?size-offset:4096;if(!read(offset,n))return 2;std::memcpy(image+offset,rx+4,n);control->progress=offset+n;}
  return 0;
 }
 // Enable the Winbond QE bit, preserving all other status-register bits, for FSBL 6Bh reads.
 tx[0]=0x35;tx[1]=0;if(!transfer(2))return 2;const uint8_t sr2=rx[1];
 if(!(sr2&2)){tx[0]=5;tx[1]=0;if(!transfer(2))return 2;const uint8_t sr1=rx[1];if(!enable_write())return 4;tx[0]=1;tx[1]=sr1;tx[2]=sr2|2;if(!transfer(3,false)||!idle(1))return 5;}
 tx[0]=0x35;tx[1]=0;if(!transfer(2)||!(rx[1]&2))return 8;
 Sha256 expected;expected.update(image,size);uint8_t digest[32];expected.finish(digest);
 for(unsigned i=0;i<32;++i)control->sha256[i]=digest[i];
 control->state=0x45524153;
 for(unsigned offset=0;offset<size;offset+=65536){if(!enable_write())return 4;address(0xd8,offset);if(!transfer(4)||!idle(5))return 5;control->progress=offset;}
 control->state=0x50524f47;
 for(unsigned offset=0;offset<size;offset+=256){unsigned n=size-offset<256?size-offset:256;if(!enable_write())return 4;address(2,offset);std::memcpy(tx+4,image+offset,n);if(!transfer(n+4,false)||!idle(1))return 5;control->progress=offset+n;}
 control->state=0x56455249;
 for(unsigned offset=0;offset<size;offset+=4096){unsigned n=size-offset<4096?size-offset:4096;if(!read(offset,n))return 2;if(std::memcmp(rx+4,image+offset,n)){control->progress=offset;return 6;}control->progress=offset+n;}
 // Verify using the same quad-output read command used by the generated FSBL.
 for(unsigned offset=0;offset<size;offset+=4096){unsigned n=size-offset<4096?size-offset:4096;address(0x6b,offset);std::memset(tx+4,0,n+1);if(!transfer(n+5))return 2;if(std::memcmp(rx+5,image+offset,n)){control->progress=offset;return 9;}control->progress=offset+n;}
 return 0;
}
int main(){Xil_DCacheDisable();control->state=0x42555359;control->progress=0;control->error=execute();control->state=0x444f4e45;while(1){}}
