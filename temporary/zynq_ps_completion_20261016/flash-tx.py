from pathlib import Path
p=Path('camera/qspi_program.cpp');s=p.read_text();s=s.replace('static bool transfer(unsigned n){return XQspiPs_PolledTransfer(&qspi,tx,rx,n)==XST_SUCCESS;}','''static bool transfer(unsigned n,bool receive=true){return XQspiPs_PolledTransfer(&qspi,tx,receive?rx:nullptr,n)==XST_SUCCESS;}''')
s=s.replace('''if(!transfer(n+4)||!idle(1))return 5;''','''if(!transfer(n+4,false)||!idle(1))return 5;''')
s=s.replace(''' Sha256 expected;''',''' // Enable the Winbond QE bit, preserving all other status-register bits, for FSBL 6Bh reads.
 tx[0]=0x35;tx[1]=0;if(!transfer(2))return 2;const uint8_t sr2=rx[1];
 if(!(sr2&2)){tx[0]=5;tx[1]=0;if(!transfer(2))return 2;const uint8_t sr1=rx[1];if(!enable_write())return 4;tx[0]=1;tx[1]=sr1;tx[2]=sr2|2;if(!transfer(3,false)||!idle(1))return 5;}
 tx[0]=0x35;tx[1]=0;if(!transfer(2)||!(rx[1]&2))return 8;
 Sha256 expected;''')
s=s.replace('''if(std::memcmp(rx+4,image+offset,n))return 6;''','''if(std::memcmp(rx+4,image+offset,n)){control->progress=offset;return 6;}''')
s=s.replace(''' return 0;
}
int main()''',''' // Verify using the same quad-output read command used by the generated FSBL.
 for(unsigned offset=0;offset<size;offset+=4096){unsigned n=size-offset<4096?size-offset:4096;address(0x6b,offset);std::memset(tx+4,0,n+1);if(!transfer(n+5))return 2;if(std::memcmp(rx+5,image+offset,n)){control->progress=offset;return 9;}control->progress=offset+n;}
 return 0;
}
int main()''')
# Quad reads need one more dummy byte beyond the four-byte command header.
s=s.replace('static uint8_t tx[4100],rx[4100];','static uint8_t tx[4104],rx[4104];')
p.write_bytes(s.encode())
